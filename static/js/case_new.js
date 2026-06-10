(function () {
  "use strict";

  const form = document.getElementById("case-form");
  const errorEl = document.getElementById("form-error");
  const imageInput = document.getElementById("image");

  if (!form) return;

  form.addEventListener("submit", function (e) {
    errorEl.classList.add("hidden");
    const file = imageInput.files[0];
    if (!file) {
      e.preventDefault();
      errorEl.textContent = "画像ファイルを選択してください。";
      errorEl.classList.remove("hidden");
      return;
    }
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["png", "jpg", "jpeg"].includes(ext)) {
      e.preventDefault();
      errorEl.textContent = "PNG / JPG のみ対応しています。";
      errorEl.classList.remove("hidden");
      return;
    }
    if (file.size > 16 * 1024 * 1024) {
      e.preventDefault();
      errorEl.textContent = "ファイルサイズは16MB以下にしてください。";
      errorEl.classList.remove("hidden");
    }
  });
})();
