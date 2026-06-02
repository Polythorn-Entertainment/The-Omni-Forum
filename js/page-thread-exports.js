/* Window exports and live snapshot handlers for the thread page */

window.refreshCurrentPage = refreshCurrentPage;
window.submitReply = submitReply;
window.toggleLike = toggleLike;
window.toggleReaction = toggleReaction;
window.toggleAcceptedAnswer = toggleAcceptedAnswer;
window.submitThreadPollVote = submitThreadPollVote;
window.togglePollClosed = togglePollClosed;
window.quotePost = quotePost;
window.toggleThreadBookmark = toggleThreadBookmark;
window.toggleThreadSubscription = toggleThreadSubscription;
window.showPostHistory = showPostHistory;
window.showEditPostModal = showEditPostModal;
window.savePostEdit = savePostEdit;
window.showThreadSettingsModal = showThreadSettingsModal;
window.saveThreadSettings = saveThreadSettings;
window.toggleThreadModeration = toggleThreadModeration;
window.showSplitThreadModal = showSplitThreadModal;
window.submitSplitThread = submitSplitThread;
window.deletePost = deletePost;
window.deleteThread = deleteThread;
window.goToThreadPage = goToThreadPage;
window.clearReplyDraft = clearReplyDraft;
window.insertComposerToken = insertComposerToken;
window.removeReplyUpload = removeReplyUpload;
window.updateReplyUploadAlt = updateReplyUploadAlt;
window.applyReplyMention = applyReplyMention;
window.getLiveContext = () => ({
  threadId: currentThread?.id || queryParam("thread") || "",
});
window.handleLiveSnapshot = (snapshot) => {
  const thread = snapshot?.thread;
  if (!thread || !currentThread || Number(thread.id) !== Number(currentThread.id)) return;
  if (
    Number(thread.postCount || 0) !== Number(currentPosts.length || 0)
    || Number(thread.lastPostId || 0) !== Number(currentPosts[currentPosts.length - 1]?.id || 0)
  ) {
    scheduleThreadLiveRefresh();
  }
};
