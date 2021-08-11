// appointment.js
// 获取应用实例
const app = getApp()

Page({
  data: {
    sum: 0,
    page: 1,
    items: [{name:"RTX3060",id:1001,available:true,['brief-intro']:'为降低温度及我觉得大姐大街我i大家',thumbnail:"../../icon/add.png"}],

    userInfo: {},
    hasUserInfo: false,
    canIUseGetUserProfile: false,
    canIUseOpenData: false,

    servers: '',
    loading: true,
    imgUrls: [
      'https://zos.alipayobjects.com/rmsportal/AiyWuByWklrrUDlFignR.png',
      'https://zos.alipayobjects.com/rmsportal/TekJlZRVCjLFexlOCuWn.png',
      'https://zos.alipayobjects.com/rmsportal/IJOtIlfsYdTyaDTRVrLI.png',
    ],
  },
  onReachBottom() {
    wx.showLoading({
      mask: true,
      title: '加载中',
    })
    if (this.data.page * 20 < this.data.sum) {
      wx.request({
        url: app.globalData.url + '/item?p=<page>/',
        data: {
          p: this.data.page
        },
        method: 'GET',
        success: (res) => {
          if (res.data.code == 0) {
            this.setData({
              page: this.data.page + 1,
              sum: res.data['item-count'],
              items: this.data.items.concat(res.data.items)
            })
            wx.hideLoading();
          } else {
            console.log(res.data.code, res.data.errmsg)
            wx.hideLoading();
            wx.showToast({
              title: '连接错误',
              icon: 'error',
              duration: 1500
            })
          }
        },
        fail: (res) => {
          console.log(res.data.code, res.data.errmsg)
          wx.hideLoading();
          wx.showToast({
            title: '连接失败',
            icon: 'error',
            duration: 1500
          });
          stop = true;
        }
      });
    } else {
      wx.hideLoading();
      wx.showToast({
        title: '没有更多了',
        icon: 'none',
        duration: 1500
      });
    }
  },
  onLoad() {
    if (wx.getUserProfile) {
      this.setData({
        canIUseGetUserProfile: true
      })
    }
    wx.setNavigationBarTitle({
      title: '预约设备'
    })
    wx.showLoading({
      mask: true,
      title: '加载中',
    })
    wx.request({
      url: app.globalData.url + '/item?p=<page>/',
      data: {
        p: this.data.page
      },
      method: 'GET',
      success: (res) => {
        if (res.data.code == 0) {
          this.setData({
            page: this.data.page + 1,
            sum: res.data['item-count'],
            items: this.data.items.concat(res.data.items)
          })
          wx.hideLoading();
        } else {
          console.log(res.data.code, res.data.errmsg)
          wx.hideLoading();
          wx.showToast({
            title: '连接错误',
            icon: 'error',
            duration: 1500
          })
        }
      },
      fail: (res) => {
        console.log(res.data.code, res.data.errmsg)
        wx.hideLoading();
        wx.showToast({
          title: '连接失败',
          icon: 'error',
          duration: 1500
        });
      }
    });
  },
  chooseMe(e) {
    let value = e.currentTarget.dataset.value
    if (app.globalData.login == false) {
      wx.showToast({
        title: '未成功登录',
        icon: 'error',
        duration: 1000
      });
    } else if (app.globalData.userInfo) {
      wx.navigateTo({
        url: 'admit/admit?id=' + this.data.items[value].id + '&name=' + this.data.items[value].name
      })
    } else {
      wx.showToast({
        title: '未绑定信息',
        icon: 'error',
        duration: 1000
      });
      setTimeout(function () {
        wx.navigateTo({
          url: '../bind/bind'
        })
      }, 1000)
    }
  },
  //测试专用
  great() {
    if (app.globalData.userInfo)
      app.globalData.userInfo = false
    else
      app.globalData.userInfo = true
  },
  better() {
    if (app.globalData.login)
      app.globalData.login = false
    else
      app.globalData.login = true
  },
  evolve() {
    if (app.globalData.isadmin)
      app.globalData.isadmin = false
    else
      app.globalData.isadmin = true
  },
})