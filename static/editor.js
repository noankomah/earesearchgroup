(function () {
  function setup() {
    document.querySelectorAll('[data-editor]').forEach(function (wrapper) {
      if (wrapper.dataset.ready) return;
      wrapper.dataset.ready = '1';
      const textarea = wrapper.querySelector('textarea');
      const editor = wrapper.querySelector('[contenteditable]');
      if (!textarea || !editor) return;
      editor.innerHTML = textarea.value;
      editor.hidden = false;
      textarea.hidden = true;
      const sync = function () { textarea.value = editor.innerHTML; };
      editor.addEventListener('input', sync);
      editor.addEventListener('paste', function (event) {
        event.preventDefault();
        document.execCommand('insertText', false, event.clipboardData.getData('text/plain'));
        sync();
      });
      editor.addEventListener('drop', function (event) { event.preventDefault(); });
      wrapper.querySelectorAll('[data-command]').forEach(function (button) {
        button.addEventListener('mousedown', function (event) { event.preventDefault(); });
        button.addEventListener('click', function () {
          editor.focus();
          let value = button.dataset.value || null;
          if (button.dataset.command === 'createLink') {
            value = window.prompt('Link address (https://, mailto:, or /site-path):');
            if (!value || !/^(https?:\/\/|mailto:|tel:|\/(?!\/)|#)/i.test(value) || /[\s\\\u0000-\u001f]/.test(value)) return;
          }
          document.execCommand(button.dataset.command, false, value);
          sync();
        });
      });
      wrapper.closest('form').addEventListener('submit', sync);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup); else setup();
  document.addEventListener('formset:added', setup);
}());
