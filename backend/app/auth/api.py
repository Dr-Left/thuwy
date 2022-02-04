from flask import request, session
import requests as R
import requests.exceptions as RE
import json as Json
import time as Time
import functools
import os
import traceback

from app.auth import util

from . import authRouter
from config import WX_APP_ID, WX_APP_SECRET, config
from app import adminReqIdPool
from app.comerrs import *
from .errcode import *
import app.checkargs as CheckArgs
from app import timetools as timestamp

from .model import (
    OAUTH_CODE_LEN,
    OAUTH_TOKEN_LEN,
    OAuthReqScope,
    OAuthRequest,
    OAuthToken,
    db,
    Admin,
    AdminRequest,
    User,
    UserBinding,
)
from .model import Scope


@authRouter.route("/login/", methods=["POST"])
def login():
    data: dict = request.get_json()
    if not data or not data.get("code", None):
        return CODE_ARG_MISSING

    try:
        res = R.get(
            f"https://api.weixin.qq.com/sns/jscode2session?"
            + f"appid={WX_APP_ID}&secret={WX_APP_SECRET}&"
            + f"js_code={data['code']}&grant_type=authorization_code",
            timeout=5,
        )

        if res.status_code != 200:
            return CODE_LOGIN_NOT_200

        resJson: dict = Json.loads(res.text)
        if (
            "openid" not in resJson
            or not resJson["openid"]
            or "session_key" not in resJson
            or not resJson["session_key"]
        ):

            # print(C.Red('incomplete wx res'), end='')
            # pprint(resJson)
            return CODE_LOGIN_INCOMPLETE_WX_RES

        if "errcode" in resJson and resJson["errcode"] != 0:
            rtn = {}
            rtn.update(CODE_LOGIN_WEIXIN_REJECT)
            rtn.update(
                {"wx-code": resJson["errcode"], "wx-errmsg": resJson.get("errmsg", "")}
            )
            return rtn

        openid = str(resJson["openid"])
        session["wx-skey"] = str(resJson["session_key"])
        session["openid"] = openid
        session.permanent = True
    except RE.Timeout:
        return CODE_LOGIN_TIMEOUT
    except RE.ConnectionError as e:
        return CODE_LOGIN_CNT_ERROR
    except Exception as e:
        # print(C.Red(str(e)))
        # pprint(resJson)
        return CODE_LOGIN_UNKOWN

    user = (
        db.session.query(User.openid, User.schoolId)
        .filter(User.openid == openid)
        .limit(1)
        .one_or_none()
    )

    if user == None:
        db.session.add(User(openid))
        db.session.commit()
        user = (None, None)

    rtn = {}
    rtn.update(CODE_SUCCESS)
    rtn["bound"] = user[1] != None
    return rtn


def requireLogin(handler):
    @functools.wraps(handler)
    def inner(*args, **kwargs):
        # if skipLoginAndBind and not session.get('openid', None):
        #     session['openid'] = 'openid for debug'
        #     session['wx-skey'] = 'secret key for debug'
        #     return handler(*args, **kwargs)
        if not session.get("openid"):
            return CODE_NOT_LOGGED_IN
        elif not User.fromOpenid(session.get("openid")):
            # return CODE_NOT_LOGGED_IN # 这里意味着用户登录过，但数据库中没有记录，多半是管理员删库了
            return CODE_DATABASE_ERROR
        else:
            return handler(*args, **kwargs)

    return inner


def didilogin():
    if not session.get("openid"):
        return "no"
    elif not User.fromOpenid(session.get("openid")):
        return "yes but database lost your record."
    else:
        return "yes"


def requireBinding(handler):
    @functools.wraps(handler)
    def inner(*args, **kwargs):
        openid = session["openid"]
        schoolId = (
            db.session.query(User.schoolId)
            .filter(User.openid == openid)
            .one_or_none()[0]
        )  # 这里可以安全的直接使用[0]，因为这个函数总在 requireLogin 后调用

        if schoolId == None:
            return CODE_UNBOUND
        else:
            return handler(*args, **kwargs)

    return inner


def didibind():
    if didilogin() == "skipped":
        return "skipped"
    if "no" in didilogin():
        return "no and check your login state"
    openid = session["openid"]
    schoolId = (
        db.session.query(User.schoolId).filter(User.openid == openid).one_or_none()
    )
    if not schoolId:
        return "no and database lost your record"
    if not schoolId[0]:
        return "no"
    else:
        return "yes"


def requireAdmin(handler):
    @functools.wraps(handler)
    def inner(*args, **kwargs):
        # if skipAdmin:
        #     return handler(*args, **kwargs)

        openid = session["openid"]
        exist = (
            db.session.query(Admin.openid).filter(Admin.openid == openid).one_or_none()
        )
        if exist:
            return handler(*args, **kwargs)
        else:
            return CODE_NOT_ADMIN

    return inner


def amiadmin():
    if didilogin() != "yes":
        return "no and you did not login"
    if didibind() != "yes":
        return "no and you did not bind"
    openid = session["openid"]
    exist = db.session.query(Admin.openid).filter(Admin.openid == openid).one_or_none()
    if exist:
        return "yes"
    else:
        return "no"


@authRouter.route("/bind/", methods=["POST"])
@requireLogin
def bind():

    reqJson: dict = request.get_json()
    if (
        not reqJson
        or "id" not in reqJson
        or not reqJson["id"]
        or "name" not in reqJson
        or not reqJson["name"]
        or "clazz" not in reqJson
        or not reqJson["clazz"]
    ):
        return CODE_ARG_MISSING

    try:
        schoolId = str(reqJson["id"])
        name = str(reqJson["name"])
        clazz = str(reqJson["clazz"])
    except:
        return CODE_ARG_TYPE_ERR

    openid = session["openid"]
    user = User.fromOpenid(openid)

    if user.schoolId != None:
        return CODE_ALREADY_BOUND

    bdnInfo = UserBinding.check(schoolId, name, clazz)
    if bdnInfo == None:
        return CODE_INVALID_BIND
    if bdnInfo.openid != None:
        return CODE_TARGET_BOUND

    try:
        user.name = name
        user.schoolId = schoolId
        user.clazz = clazz
        bdnInfo.openid = openid

        db.session.commit()
    except:
        traceback.print_exc()
        return CODE_DATABASE_ERROR

    return CODE_SUCCESS


@authRouter.route("/profile/")
@requireLogin
def getMyProfile():
    rtn = User.queryProfile(session["openid"])
    if rtn == None:
        return CODE_ARG_INVALID
    rtn.update(CODE_SUCCESS)
    return rtn


@authRouter.route("/profile/<openId>/", methods=["GET"])
@requireLogin
@requireBinding
@requireAdmin
def getProfile(openId):
    openId = str(openId)
    profile = User.queryProfile(openId)
    if profile == None:
        return CODE_ARG_INVALID
    profile.update(CODE_SUCCESS)
    return profile


@authRouter.route("/admin/request/", methods=["POST"])
@requireLogin
@requireBinding
def requestAdmin():

    exist = Admin.fromId(session["openid"])
    if exist:
        return CODE_ALREADY_ADMIN

    exist = (
        db.session.query(AdminRequest)
        .filter(AdminRequest.requestor == session["openid"])
        .filter(AdminRequest.state == 0)
        .first()
    )
    if exist:
        return CODE_ALREADY_REQUESTED

    try:
        req = AdminRequest()
        req.id = adminReqIdPool.next()
        req.requestor = session["openid"]
        req.state = 0
        db.session.add(req)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return CODE_DATABASE_ERROR

    rtn = {"id": req.id}
    rtn.update(CODE_SUCCESS)
    return rtn


@authRouter.route("/admin/request/", methods=["GET"])
@requireLogin
@requireBinding
@requireAdmin
def adminReqList():
    qryRst = db.session.query(AdminRequest).filter(AdminRequest.state == 0).all()

    arr = []
    for r in qryRst:
        arr.append(r.toDict())

    rtn = {"list": arr}
    rtn.update(CODE_SUCCESS)
    return rtn


@authRouter.route("/admin/request/<int:reqId>/", methods=["POST"])
@requireLogin
@requireBinding
@requireAdmin
def examAdminReq(reqId):
    adminReq = AdminRequest.fromId(reqId)
    if not adminReq:
        return CODE_ARG_INVALID
    if adminReq.state != 0:
        return CODE_ARG_INVALID
    # TODO: 细分ErrCode

    json = request.get_json()
    if not CheckArgs.hasAttrs(json, ["pass", "reason"]):
        return CODE_ARG_MISSING

    if json["pass"] == 1:
        adminReq.state = 1
        admin = Admin()
        admin.openid = adminReq.requestor
        db.session.add(admin)
    elif json["pass"] == 0:
        adminReq.state = 2
    else:
        return CODE_ARG_INVALID

    adminReq.reason = json["reason"]
    adminReq.approver = session["openid"]

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return CODE_DATABASE_ERROR

    return CODE_SUCCESS


@authRouter.route("/admin/<openid>/", methods=["DELETE"])
@requireLogin
@requireBinding
@requireAdmin
def delAdmin(openid):
    openid = str(openid)
    admin = Admin.fromId(openid)
    if not admin:
        return CODE_ARG_INVALID

    db.session.delete(admin)
    try:
        db.session.commit()
    except:
        traceback.print_exc()
        return CODE_DATABASE_ERROR
    return CODE_SUCCESS


if getattr(config, "ENABLE_TEST_ACCOUNT", False):
    print(
        "!!Warning!! Running with testing mode, enable testing account auto-creation."
    )

    @authRouter.route("/test/login/")
    def loginTestAccount():
        rint = 0
        for b in os.urandom(64):
            rint += b
        rint %= 10000000000
        fakeOpenId = f"test-account-{rint}"

        existAccount = User.fromOpenid(fakeOpenId)
        if existAccount:
            existAdmin = Admin.fromId(fakeOpenId)
            if existAdmin:
                db.session.delete(existAdmin)
            db.session.delete(existAccount)
            db.session.commit()

        newAccount = User(fakeOpenId)
        mode = request.args.get("mode", "user")
        if mode == "admin":
            newAccount.name = f"TAdmin {rint}"
            admin = Admin()
            admin.openid = fakeOpenId
            db.session.add(admin)
        else:
            newAccount.name = f"TUser {rint}"

        newAccount.schoolId = f"{rint}"
        newAccount.clazz = f"未央-测试"
        db.session.add(newAccount)

        try:
            db.session.commit()
        except:
            return CODE_DATABASE_ERROR

        session["openid"] = fakeOpenId
        session.permanent = True

        return CODE_SUCCESS


@authRouter.route("/admin/")
@requireLogin
@requireBinding
@requireAdmin
def getAdminList():

    profileArr = []

    qryRst = db.session.query(Admin).all()
    for admin in qryRst:
        profileArr.append(User.fromOpenid(admin.openid).toDict())

    rtn = {}
    rtn.update(CODE_SUCCESS)
    rtn["profiles"] = profileArr
    return rtn


@authRouter.route("/user/")
@requireLogin
@requireBinding
@requireAdmin
def getUserList():
    PageLimit = 30

    clazz = request.args.get("clazz", None)
    page = request.args.get("p", 1, int)

    qry = db.session.query(User)
    if clazz:
        qry = qry.filter(User.clazz == clazz)

    qry = qry.limit(PageLimit).offset((page - 1) * PageLimit)

    qryRst = qry.all()
    proArr = [e.toDict() for e in qryRst]

    rtn = {}
    rtn.update(CODE_SUCCESS)
    rtn["profiles"] = proArr
    return rtn


@authRouter.route("/user/<openid>/", methods=["DELETE"])
def unbindUser(openid):
    if not openid:
        return CODE_ARG_INVALID

    user = User.fromOpenid(openid)
    ubdn: UserBinding = UserBinding.fromOpenId(openid)

    if not user:
        return CODE_USER_NOT_FOUND

    if not ubdn:
        return CODE_DATABASE_CONSISTANCE_ERROR

    user.schoolId = None
    user.name == None
    user.clazz = None
    ubdn.openid = None

    try:
        db.session.commit()
    except:
        traceback.print_exc()
        return CODE_DATABASE_ERROR

    return CODE_SUCCESS


@authRouter.route("/oauth/authorize/", methods=["POST"])
def requestOAuth():
    json = request.json
    if not json:
        return CODE_ARG_INVALID
    if "scopes" not in json:
        return CODE_ARG_MISSING

    scopeList = []
    for e in json["scopes"]:
        if not CheckArgs.isStr(e):
            return CODE_ARG_TYPE_ERR
        scope = Scope.fromScopeStr(e)
        if not scope:
            return CODE_ARG_INVALID
        scopeList.append(scope)

    code = util.randomString(OAUTH_CODE_LEN)
    exist = (
        db.session.query(OAuthRequest)
        .filter(OAuthRequest.code == code)
        .filter(OAuthRequest.expireAt >= timestamp.now())
        .filter(OAuthRequest.reject == 0)
        .one_or_none()
    )

    if exist:
        return CODE_OAUTH_RETRY

    oauthReq = OAuthRequest()
    oauthReq.code = code
    oauthReq.expireAt = timestamp.clockAfter(timestamp.now(), 0, 5)
    db.session.add(oauthReq)

    try:
        db.session.commit()  # 先提交一次，让oauthReq生成ID
    except:
        return CODE_DATABASE_ERROR

    for s in scopeList:
        s: Scope
        reqScope = OAuthReqScope()
        reqScope.scopeId = s.id
        reqScope.reqId = oauthReq.id
        db.session.add(reqScope)

    try:
        db.session.commit()
    except:
        return CODE_DATABASE_ERROR

    rtn = {}
    rtn.update(CODE_SUCCESS)
    rtn.update(oauthReq.toDict())
    return rtn


def getOAuthInfo(oauthReq):
    if oauthReq.reject:
        return CODE_OAUTH_REJECT

    if not oauthReq.token:
        return CODE_OAUTH_HOLDON
    
    rtn = {
        "token": oauthReq.token.token,
        "expire_at": oauthReq.token.expireAt,
        "scopes": [e.scope.toDict() for e in oauthReq.scopes],
    }
    rtn.update(CODE_SUCCESS)
    return rtn


def grantOAuth(oauthReq: OAuthRequest):
    openid = session.get("openid")
    if not openid:
        return CODE_NOT_LOGGED_IN
    
    if oauthReq.reject: # 拒绝后重复
        return CODE_OAUTH_REJECT
    
    if oauthReq.token != None: # 授权后重复
        rtn = {"token": oauthReq.token.token, 'expire_at': oauthReq.token.expireAt}
        rtn.update(CODE_SUCCESS)
        return rtn
    
    json = request.json
    if not json:
        return CODE_ARG_INVALID
    if 'authorize' not in json:
        return CODE_ARG_MISSING
    
    if json['authorize'] == 'grant':
        tokenStr = util.randomString(OAUTH_TOKEN_LEN)
        token = (
            db.session.query(OAuthToken)
            .filter(OAuthToken.expireAt >= timestamp.now())
            .filter(OAuthToken.token == tokenStr)
            .one_or_none()
        )
        if token:
            return CODE_OAUTH_RETRY  # 生成的token str重复了

        token = OAuthToken()
        token.token = tokenStr
        token.expireAt = timestamp.daysAfter(7)
        token.ownerId = openid
        token.reqId = oauthReq.id
        try:
            db.session.add(token)
            db.session.commit()
        except:
            return CODE_DATABASE_ERROR
        
        for reqScope in oauthReq.scopes:
            reqScope.tokenId = token.id
        
        try:
            db.session.commit()
        except:
            return CODE_DATABASE_ERROR
        
        rtn = {'token': token.token, 'expire_at': token.expireAt}
        rtn.update(CODE_SUCCESS)
        return rtn
    
    elif json['authorize'] == 'reject':
        try:
            oauthReq.reject = 1
            db.session.commit()
        except:
            return CODE_DATABASE_ERROR
        return CODE_SUCCESS
    
    else:
        return CODE_ARG_INVALID


@authRouter.route("/oauth/authorize/<authCode>/", methods=["GET", "POST"])
def modifyOAuth(authCode):
    if not authCode:
        return CODE_ARG_MISSING
    oauthReq: OAuthRequest = (
        db.session.query(OAuthRequest)
        .filter(OAuthRequest.expireAt >= timestamp.now())
        .filter(OAuthRequest.code == authCode)
        .one_or_none()
    )
    if not oauthReq:
        return CODE_ARG_INVALID

    if request.method == "GET":
        return getOAuthInfo(oauthReq)
    elif request.method == "POST":
        return grantOAuth(oauthReq)
