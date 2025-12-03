// library_system/static/js/post_interactions.js

(() => {
  if (window.BHPostInteractions) {
    return;
  }

  const commentsModal = document.getElementById('comments-modal');
  const commentsList = document.getElementById('comments-list');
  const commentsForm = document.getElementById('comments-form');
  const commentInput = document.getElementById('comment-input');
  const commentsPostContent = document.getElementById('comments-post-content');
  const commentsClose = document.getElementById('comments-close');
  const imageViewerModal = document.getElementById('image-viewer-modal');
  const imageViewerImg = document.getElementById('image-viewer-img');
  const imageViewerVideo = document.getElementById('image-viewer-video');
  const imageViewerCounter = document.getElementById('image-viewer-counter');
  const imageViewerPrev = document.getElementById('image-viewer-prev');
  const imageViewerNext = document.getElementById('image-viewer-next');
  const imageViewerClose = document.getElementById('image-viewer-close');

  const state = {
    currentComments: null,
    viewerImages: [],
    viewerIndex: 0,
  };

  function getCsrfToken() {
    const input = document.querySelector('input[name=csrfmiddlewaretoken]');
    if (input) {
      return input.value;
    }
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function escapeHtml(value) {
    if (value === undefined || value === null) return '';
    return String(value).replace(/[&<>"']/g, (char) => {
      switch (char) {
        case '&':
          return '&amp;';
        case '<':
          return '&lt;';
        case '>':
          return '&gt;';
        case '"':
          return '&quot;';
        case "'":
          return '&#39;';
        default:
          return char;
      }
    });
  }

  function formatLocation(value) {
    if (!value) return '';
    if (typeof value === 'object') {
      const parts = [
        value.province || value.state || '',
        value.city || '',
        value.barangay || '',
        value.address || value.display_name || '',
      ].filter((part) => part && String(part).trim());
      return parts.join(', ');
    }
    if (typeof value === 'string') {
      try {
        const parsed = JSON.parse(value);
        if (parsed && typeof parsed === 'object') {
          return formatLocation(parsed);
        }
      } catch (err) {
        // ignore parsing error and fall through
      }
      return value;
    }
    return String(value);
  }

  function apiBaseForSource(source) {
    return source === 'student' ? '/students' : '/properties';
  }

  async function toggleLikeRequest(postId, source) {
    const base = apiBaseForSource(source);
    const response = await fetch(`${base}/api/post/${source}/${postId}/toggle-like/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
      },
    });
    if (!response.ok) {
      throw new Error('Failed to toggle reaction');
    }
    return response.json();
  }

  async function fetchComments(postId, source) {
    const base = apiBaseForSource(source);
    const response = await fetch(`${base}/api/post/${source}/${postId}/comments/`);
    if (!response.ok) {
      throw new Error('Failed to load comments');
    }
    return response.json();
  }

  async function submitComment(postId, source, text) {
    const base = apiBaseForSource(source);
    const response = await fetch(`${base}/api/post/${source}/${postId}/comments/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      throw new Error('Failed to add comment');
    }
    return response.json();
  }

  function updateLikeButtons(postId, liked, likeCount) {
    document.querySelectorAll(`article[data-post-id="${postId}"] .like-btn`).forEach((btn) => {
      const icon = btn.querySelector('svg');
      const countEl = btn.querySelector('.like-count');
      if (countEl) countEl.textContent = likeCount;
      btn.dataset.liked = liked ? 'true' : 'false';
      if (liked) {
        btn.classList.add('text-red-500');
        btn.classList.remove('text-text-muted');
        if (icon) icon.setAttribute('fill', 'currentColor');
      } else {
        btn.classList.remove('text-red-500');
        btn.classList.add('text-text-muted');
        if (icon) icon.setAttribute('fill', 'none');
      }
    });
  }

  function updateCommentButtons(postId, count) {
    document.querySelectorAll(`article[data-post-id="${postId}"] .comments-btn`).forEach((btn) => {
      btn.textContent = `Comments (${count})`;
    });
  }

  function renderPostHeader(post) {
    const locationText = formatLocation(post.location);
    const locationHtml = locationText
      ? `<p class="text-xs text-text-muted mt-1">📍 ${escapeHtml(locationText)}</p>`
      : '';
    const authorPic = post.author_profile_picture || '';
    const authorInitial = (post.author_name || 'U').charAt(0).toUpperCase();
    const imagesHtml = (post.images || [])
      .map(
        (img, idx) =>
          `<img src="${img}" class="comments-modal-media rounded-xl w-full h-40 object-cover border border-white/10 cursor-pointer" data-index="${idx}">`
      )
      .join('');
    return `
      <div class="flex items-start space-x-3 mb-4">
        <div class="w-10 h-10 rounded-full bg-neon-cyan/20 border border-neon-cyan/60 flex items-center justify-center text-neon-cyan font-bold overflow-hidden flex-shrink-0">
          ${authorPic ? `<img src="${authorPic}" alt="${post.author_name || 'User'}" class="w-full h-full object-cover">` : authorInitial}
        </div>
        <div class="flex-1">
          <p class="text-white font-medium">${escapeHtml(post.author_name || 'Anonymous')}</p>
          ${locationHtml}
          <p class="text-xs text-text-muted mt-1">${post.timestamp || ''}</p>
        </div>
      </div>
      <p class="text-text-muted text-sm mb-4 whitespace-pre-wrap">${escapeHtml(post.message || '')}</p>
      ${
        imagesHtml
          ? `<div class="grid grid-cols-2 gap-3 mb-4">${imagesHtml}</div>`
          : ''
      }
    `;
  }

  function renderComments(comments, postId, source) {
    if (!commentsList) return;
    if (!comments || !comments.length) {
      commentsList.innerHTML = '<p class="text-text-muted text-sm text-center">No comments yet.</p>';
      return;
    }
    commentsList.innerHTML = comments
      .map(
        (comment) => {
          const authorPic = comment.author_profile_picture || '';
          const authorInitial = (comment.author || 'A').charAt(0).toUpperCase();
          return `
        <div class="rounded-2xl bg-white/5 border border-white/10 p-3 mb-3" data-comment-id="${comment.id}">
          <div class="flex items-start space-x-3">
            <div class="w-8 h-8 rounded-full bg-neon-cyan/20 border border-neon-cyan/60 flex items-center justify-center text-neon-cyan font-bold text-xs flex-shrink-0 overflow-hidden">
              ${authorPic ? `<img src="${authorPic}" alt="${comment.author}" class="w-full h-full object-cover">` : authorInitial}
            </div>
            <div class="flex-1">
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs font-medium text-white">${escapeHtml(comment.author || 'Anonymous')}</span>
                <span class="text-xs text-text-muted">${comment.timestamp}</span>
              </div>
              <p class="text-sm text-white mb-2 whitespace-pre-wrap">${escapeHtml(comment.text || '')}</p>
              <div class="flex items-center space-x-4 text-xs">
                <button class="comment-like-btn flex items-center space-x-1 text-text-muted hover:text-red-500 transition" data-comment-id="${comment.id}" data-liked="${comment.liked || 'false'}">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="${comment.liked ? 'currentColor' : 'none'}" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                  </svg>
                  <span class="comment-like-count">${comment.likes || 0}</span>
                </button>
                <button class="comment-reply-btn text-text-muted hover:text-neon-cyan transition">Reply</button>
                ${comment.is_author ? `
                <div class="relative">
                  <button class="comment-actions-btn text-text-muted hover:text-neon-cyan text-lg" data-comment-id="${comment.id}">⋮</button>
                  <div id="comment-actions-menu-${comment.id}" class="hidden absolute right-0 top-6 glass-card rounded-xl border border-white/10 p-2 z-10 min-w-[100px] shadow-xl">
                    <button class="comment-edit-btn block w-full text-left px-3 py-2 rounded-lg text-xs text-neon-cyan hover:bg-white/10" data-comment-id="${comment.id}">Edit</button>
                    <button class="comment-delete-btn block w-full text-left px-3 py-2 rounded-lg text-xs text-red-300 hover:bg-red-500/20" data-comment-id="${comment.id}">Delete</button>
                  </div>
                </div>
                ` : ''}
              </div>
            </div>
          </div>
        </div>
      `;
        }
      )
      .join('');
  }

  function openCommentsModal(postId, source, payload) {
    if (!commentsModal || !commentsList) return;
    commentsPostContent.innerHTML = renderPostHeader(payload.post);
    renderComments(payload.comments, postId, source);
    state.currentComments = {
      postId,
      source,
      count: payload.comment_count || payload.comments.length || 0,
    };
    updateCommentButtons(postId, state.currentComments.count);
    commentsModal.classList.remove('hidden');
    
    // Attach click handlers for comment media
    setTimeout(() => {
      commentsPostContent.querySelectorAll('.comments-modal-media').forEach((media) => {
        const idx = parseInt(media.dataset.index || '0', 10);
        media.addEventListener('click', () => {
          const images = payload.post.images || [];
          if (images.length) {
            openImageViewer(images, idx);
          }
        });
      });
    }, 100);
  }

  function closeCommentsModal() {
    if (!commentsModal) return;
    commentsModal.classList.add('hidden');
    state.currentComments = null;
    if (commentInput) commentInput.value = '';
  }

  function openImageViewer(images, startIndex = 0) {
    if (!imageViewerModal || !images || !images.length) return;
    state.viewerImages = images;
    state.viewerIndex = startIndex;

    function showMedia(index) {
      const url = state.viewerImages[index];
      const isVideo =
        typeof url === 'string' && (url.includes('.mp4') || url.includes('video'));
      if (isVideo) {
        imageViewerImg.classList.add('hidden');
        imageViewerVideo.classList.remove('hidden');
        imageViewerVideo.src = url;
      } else {
        imageViewerVideo.classList.add('hidden');
        imageViewerImg.classList.remove('hidden');
        imageViewerImg.src = url;
      }
      if (imageViewerCounter) {
        imageViewerCounter.textContent = `${index + 1} / ${state.viewerImages.length}`;
      }
    }

    showMedia(state.viewerIndex);
    imageViewerModal.classList.remove('hidden');

    if (imageViewerPrev) {
      imageViewerPrev.onclick = (e) => {
        e.preventDefault();
        state.viewerIndex =
          (state.viewerIndex - 1 + state.viewerImages.length) % state.viewerImages.length;
        showMedia(state.viewerIndex);
      };
    }
    if (imageViewerNext) {
      imageViewerNext.onclick = (e) => {
        e.preventDefault();
        state.viewerIndex = (state.viewerIndex + 1) % state.viewerImages.length;
        showMedia(state.viewerIndex);
      };
    }
    if (imageViewerClose) {
      imageViewerClose.onclick = (e) => {
        e.preventDefault();
        imageViewerModal.classList.add('hidden');
      };
    }
    imageViewerModal.onclick = (e) => {
      if (e.target === imageViewerModal) {
        imageViewerModal.classList.add('hidden');
      }
    };
  }

  async function handleLikeClick(button) {
    const article = button.closest('article[data-post-id]');
    if (!article || article.dataset.server !== 'true') return false;
    const postId = article.dataset.postId;
    const source = article.dataset.source || 'property';
    try {
      button.dataset.loading = 'true';
      const data = await toggleLikeRequest(postId, source);
      if (data.success) {
        updateLikeButtons(postId, data.liked, data.likes);
      } else {
        throw new Error(data.error || 'Failed to react.');
      }
    } catch (error) {
      console.error('toggleLike error', error);
      if (window.showMessage) {
        window.showMessage('Unable to update reaction.', 'error');
      }
    } finally {
      delete button.dataset.loading;
    }
    return true;
  }

  async function handleCommentsClick(button) {
    const article = button.closest('article[data-post-id]');
    if (!article || article.dataset.server !== 'true') return false;
    const postId = article.dataset.postId;
    const source = article.dataset.source || 'property';
    try {
      const data = await fetchComments(postId, source);
      if (!data.success) {
        throw new Error(data.error || 'Failed to load comments');
      }
      openCommentsModal(postId, source, data);
    } catch (error) {
      console.error('comments error', error);
      if (window.showMessage) {
        window.showMessage('Unable to load comments.', 'error');
      }
    }
    return true;
  }

  function handleMediaClick(media) {
    const article = media.closest('article[data-post-id]');
    if (!article || article.dataset.server !== 'true') return false;
    const images = (() => {
      try {
        return JSON.parse(article.dataset.images || '[]');
      } catch (err) {
        return [];
      }
    })();
    if (!images.length) return true;
    const index = parseInt(media.dataset.index || '0', 10);
    openImageViewer(images, Number.isNaN(index) ? 0 : index);
    return true;
  }

  function openEditPostModal(postId, source, currentMessage) {
    const modal = document.getElementById('edit-post-modal');
    const contentInput = document.getElementById('edit-post-content');
    const form = document.getElementById('edit-post-form');
    const closeBtn = document.getElementById('edit-post-modal-close');
    const cancelBtn = document.getElementById('cancel-edit-post');
    
    if (!modal || !contentInput || !form) return;
    
    contentInput.value = currentMessage || '';
    modal.classList.remove('hidden');
    
    const closeModal = () => {
      modal.classList.add('hidden');
      contentInput.value = '';
    };
    
    if (closeBtn) closeBtn.onclick = closeModal;
    if (cancelBtn) cancelBtn.onclick = closeModal;
    modal.onclick = (e) => {
      if (e.target === modal) closeModal();
    };
    
    form.onsubmit = async (e) => {
      e.preventDefault();
      const newMessage = contentInput.value.trim();
      if (!newMessage) return;
      
      try {
        const base = apiBaseForSource(source);
        const response = await fetch(`${base}/api/post/${source}/${postId}/edit/`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ message: newMessage }),
        });
        const data = await response.json();
        if (data.success && data.post_html) {
          const article = document.querySelector(`article[data-post-id="${postId}"]`);
          if (article) {
            const newArticle = document.createElement('div');
            newArticle.innerHTML = data.post_html;
            article.replaceWith(newArticle.firstElementChild);
          }
          closeModal();
          if (window.showMessage) {
            window.showMessage('Post updated successfully.', 'success');
          }
        } else {
          throw new Error(data.error || 'Failed to update post');
        }
      } catch (error) {
        console.error('edit post error', error);
        if (window.showMessage) {
          window.showMessage('Unable to update post.', 'error');
        }
      }
    };
  }

  async function handleEditPost(button) {
    const article = button.closest('article[data-post-id]');
    if (!article || article.dataset.server !== 'true') return false;
    const postId = article.dataset.postId;
    const source = article.dataset.source || 'property';
    const currentMessage = article.querySelector('p.text-text-muted')?.textContent || '';
    openEditPostModal(postId, source, currentMessage);
    return true;
  }

  async function handleDeletePost(button) {
    const article = button.closest('article[data-post-id]');
    if (!article || article.dataset.server !== 'true') return false;
    const postId = article.dataset.postId;
    const source = article.dataset.source || 'property';
    
    if (!confirm('Are you sure you want to delete this post? This action cannot be undone.')) {
      return true;
    }
    
    try {
      const base = apiBaseForSource(source);
      const response = await fetch(`${base}/api/post/${source}/${postId}/delete/`, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCsrfToken(),
        },
      });
      const data = await response.json();
      if (data.success) {
        article.remove();
        if (window.showMessage) {
          window.showMessage('Post deleted successfully.', 'success');
        }
      } else {
        throw new Error(data.error || 'Failed to delete post');
      }
    } catch (error) {
      console.error('delete post error', error);
      if (window.showMessage) {
        window.showMessage('Unable to delete post.', 'error');
      }
    }
    return true;
  }

  function toggleActionsMenu(postId) {
    const menu = document.getElementById(`actions-menu-${postId}`);
    if (!menu) return;
    document.querySelectorAll('[id^="actions-menu-"]').forEach((m) => {
      if (m.id !== menu.id) m.classList.add('hidden');
    });
    menu.classList.toggle('hidden');
  }

  document.addEventListener(
    'click',
    (event) => {
      const likeBtn = event.target.closest('.like-btn');
      if (likeBtn && handleLikeClick(likeBtn)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      const commentBtn = event.target.closest('.comments-btn');
      if (commentBtn && handleCommentsClick(commentBtn)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      const mediaEl = event.target.closest('.post-media');
      if (mediaEl && handleMediaClick(mediaEl)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      const actionsBtn = event.target.closest('.post-actions-btn');
      if (actionsBtn) {
        const article = actionsBtn.closest('article[data-post-id]');
        if (article) {
          toggleActionsMenu(article.dataset.postId);
          event.preventDefault();
          event.stopImmediatePropagation();
          return;
        }
      }
      const editBtn = event.target.closest('.edit-post-btn');
      if (editBtn && handleEditPost(editBtn)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      const deleteBtn = event.target.closest('.delete-post-btn');
      if (deleteBtn && handleDeletePost(deleteBtn)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      // Close menus when clicking outside
      if (!event.target.closest('.post-actions-btn') && !event.target.closest('[id^="actions-menu-"]')) {
        document.querySelectorAll('[id^="actions-menu-"]').forEach((m) => m.classList.add('hidden'));
      }
    },
    true
  );

  if (commentsForm) {
    commentsForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!state.currentComments) return;
      const text = commentInput ? commentInput.value.trim() : '';
      if (!text) return;
      try {
        const data = await submitComment(
          state.currentComments.postId,
          state.currentComments.source,
          text
        );
        if (!data.success) {
          throw new Error(data.error || 'Unable to add comment');
        }
        if (commentInput) commentInput.value = '';
        const newCount = data.comment_count || state.currentComments.count + 1;
        state.currentComments.count = newCount;
        updateCommentButtons(state.currentComments.postId, newCount);
        // reload comments list
        const refreshed = await fetchComments(
          state.currentComments.postId,
          state.currentComments.source
        );
        if (refreshed.success) {
          renderComments(refreshed.comments, state.currentComments.postId, state.currentComments.source);
        }
        if (window.showMessage) {
          window.showMessage('Comment posted.', 'success');
        }
      } catch (error) {
        console.error('comment submit error', error);
        if (window.showMessage) {
          window.showMessage('Unable to post comment.', 'error');
        }
      }
    });
  }

  if (commentsClose) {
    commentsClose.addEventListener('click', closeCommentsModal);
  }
  if (commentsModal) {
    commentsModal.addEventListener('click', (event) => {
      if (event.target === commentsModal) {
        closeCommentsModal();
      }
    });
  }

  window.BHPostInteractions = {
    openViewer: openImageViewer,
  };
})();

