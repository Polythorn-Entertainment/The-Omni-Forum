async function submitNewThread() {
  const error = document.getElementById("newThreadError");
  const title = document.getElementById("newThreadTitle")?.value?.trim() || "";
  const prefix = document.getElementById("newThreadPrefix")?.value?.trim() || "";
  const tags = document.getElementById("newThreadTags")?.value?.trim() || "";
  const content = document.getElementById("newThreadContent")?.value?.trim() || "";
  const mediaSensitive = Boolean(document.getElementById("newThreadSensitive")?.checked);
  if (error) error.classList.remove("visible");

  try {
    const pollQuestion = document.getElementById("newThreadPollQuestion")?.value?.trim() || "";
    const pollOptions = [
      document.getElementById("newThreadPollOption1")?.value?.trim() || "",
      document.getElementById("newThreadPollOption2")?.value?.trim() || "",
      document.getElementById("newThreadPollOption3")?.value?.trim() || "",
      document.getElementById("newThreadPollOption4")?.value?.trim() || "",
    ].filter(Boolean);
    const poll = pollQuestion ? {
      question: pollQuestion,
      options: pollOptions,
      allowsMultiple: Boolean(document.getElementById("newThreadPollMultiple")?.checked),
    } : null;
    const mediaUploads = newThreadUploads;
    const data = await API.createThread(currentSection.id, { title, prefix, tags, content, mediaUploads, mediaSensitive, poll });
    clearDraft("new-thread", currentSection?.id || queryParam("section") || "");
    newThreadUploads = [];
    closeModal();
    toast("Thread posted.", "success");
    goToThread(data.thread.id);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not post this thread.";
      error.classList.add("visible");
    }
  }
}
