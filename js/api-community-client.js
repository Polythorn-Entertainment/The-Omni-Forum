Object.assign(API, {
  getLeaderboard(metric = "xp", params = {}) {
    return this.request(`/api/leaderboard${buildQuery({ metric, ...params })}`);
  },

  getNotices(status = "open") {
    return this.request(`/api/notices?status=${encodeURIComponent(status)}`);
  },

  updateNotice(noticeId, payload) {
    return this.request(`/api/notices/contact/${encodeURIComponent(noticeId)}`, {
      method: "PATCH",
      body: payload,
    });
  },
});
