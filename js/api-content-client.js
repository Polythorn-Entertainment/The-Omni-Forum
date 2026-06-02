Object.assign(API, {
  createSection(payload) {
    return this.request("/api/sections", { method: "POST", body: payload });
  },

  updateSection(sectionId, payload) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  deleteSection(sectionId) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}`, {
      method: "DELETE",
    });
  },

  getUsers(params = {}) {
    return this.request(`/api/users${buildQuery(params)}`);
  },

  getUser(userId) {
    return this.request(`/api/users/${encodeURIComponent(userId)}`);
  },

  updateUserRelationship(userId, payload) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/relationship`, {
      method: "POST",
      body: payload,
    });
  },

  updateUserRole(userId, role) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/role`, {
      method: "PATCH",
      body: { role },
    });
  },

  moderateUser(userId, payload) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/moderation`, {
      method: "POST",
      body: payload,
    });
  },

  getSection(sectionId, params = {}) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}${buildQuery(params)}`);
  },

  createThread(sectionId, payload) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}`, {
      method: "POST",
      body: payload,
    });
  },

  getThread(threadId, params = {}) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}${buildQuery(params)}`);
  },

  updateThread(threadId, payload) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  deleteThread(threadId) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}`, {
      method: "DELETE",
    });
  },

  createPost(threadId, payload) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/posts`, {
      method: "POST",
      body: payload,
    });
  },

  updatePost(postId, payload) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  getPostHistory(postId) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}`);
  },

  deletePost(postId) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}`, {
      method: "DELETE",
    });
  },

  toggleLike(postId) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}/like`, {
      method: "POST",
    });
  },

  toggleReaction(postId, emoji) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}/reactions`, {
      method: "POST",
      body: { emoji },
    });
  },

  toggleThreadBookmark(threadId) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/bookmark`, {
      method: "POST",
    });
  },

  toggleThreadSubscription(threadId) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/subscription`, {
      method: "POST",
    });
  },

  splitThread(threadId, payload) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/split`, {
      method: "POST",
      body: payload,
    });
  },

  voteThreadPoll(threadId, optionIds) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/poll`, {
      method: "POST",
      body: { optionIds },
    });
  },
});
