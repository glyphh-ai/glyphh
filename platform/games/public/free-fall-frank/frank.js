// Free Fall Frank's page: the copy buttons beside the connector's address, and one video playing at a time.
for (const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = 'Copied';
    } catch {
      button.textContent = 'Select it';
    }
    setTimeout(() => (button.textContent = 'Copy'), 2000);
  });
}

const videos = [...document.querySelectorAll('video')];
for (const video of videos) {
  video.addEventListener('play', () => videos.forEach((other) => other !== video && other.pause()));
}
