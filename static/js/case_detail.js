(function () {
  "use strict";

  const data = window.CASE_DATA;
  if (!data) return;

  const canvas = document.getElementById("annotation-canvas");
  const ctx = canvas.getContext("2d");
  const errorBanner = document.getElementById("error-banner");
  const loadingOverlay = document.getElementById("loading-overlay");
  const annotationList = document.getElementById("annotation-list");
  const noAnnotations = document.getElementById("no-annotations");
  const overallComment = document.getElementById("overall-comment");
  const providerSelect = document.getElementById("provider-select");
  const caseStatusBadge = document.getElementById("case-status-badge");

  const RANK_COLORS = { 1: "#ef4444", 2: "#eab308", 3: "#3b82f6" };
  const MANUAL_COLOR = "#94a3b8";
  const MIN_RADIUS = 0.02;

  let annotations = data.annotations.slice();
  let selectedId = null;
  let addMode = false;
  let previewImage = null;

  let dragState = null;

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.classList.remove("hidden");
  }

  function hideError() {
    errorBanner.classList.add("hidden");
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function getColor(ann) {
    if (ann.rank && RANK_COLORS[ann.rank]) return RANK_COLORS[ann.rank];
    return MANUAL_COLOR;
  }

  function annToPixel(ann) {
    const w = canvas.width;
    const h = canvas.height;
    return {
      cx: ann.x_ratio * w,
      cy: ann.y_ratio * h,
      r: ann.radius_ratio * w,
    };
  }

  function canvasCoords(evt) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (evt.clientX - rect.left) * scaleX,
      y: (evt.clientY - rect.top) * scaleY,
    };
  }

  function hitTest(x, y) {
    for (let i = annotations.length - 1; i >= 0; i--) {
      const ann = annotations[i];
      const { cx, cy, r } = annToPixel(ann);
      const dist = Math.hypot(x - cx, y - cy);
      if (dist <= r) {
        const mode = dist < r * 0.5 ? "move" : "resize";
        return { ann, mode };
      }
    }
    return null;
  }

  function drawCanvas() {
    if (!previewImage) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(previewImage, 0, 0);

    annotations.forEach(function (ann) {
      const { cx, cy, r } = annToPixel(ann);
      const color = getColor(ann);
      const alpha = ann.doctor_confirmed ? 1.0 : 0.4;
      const isSelected = ann.id === selectedId;

      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 4 : 2;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      if (ann.rank) {
        ctx.fillStyle = color;
        ctx.font = "bold 14px sans-serif";
        ctx.fillText(String(ann.rank), cx - 4, cy - r - 6);
      }

      ctx.restore();
    });
  }

  function loadImage() {
    return new Promise(function (resolve, reject) {
      const img = new Image();
      img.onload = function () {
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        previewImage = img;
        drawCanvas();
        resolve();
      };
      img.onerror = reject;
      img.src = data.imageUrl;
    });
  }

  function updateStatusBadge(status) {
    const labels = {
      uploaded: "未解析",
      ai_analyzed: "AI解析済み・未承認",
      approved: "承認済み",
    };
    caseStatusBadge.textContent = labels[status] || status;
    caseStatusBadge.className = "status-badge status-" + status;
  }

  function renderAnnotationList() {
    const existing = annotationList.querySelectorAll(".annotation-card");
    existing.forEach(function (el) { el.remove(); });

    if (annotations.length === 0) {
      noAnnotations.classList.remove("hidden");
      return;
    }
    noAnnotations.classList.add("hidden");

    const sorted = annotations.slice().sort(function (a, b) {
      if (a.rank === null && b.rank === null) return a.point_id - b.point_id;
      if (a.rank === null) return 1;
      if (b.rank === null) return -1;
      return a.rank - b.rank || a.point_id - b.point_id;
    });

    sorted.forEach(function (ann) {
      const card = document.createElement("div");
      card.className = "annotation-card rounded-lg border p-3 " +
        (ann.id === selectedId ? "selected" : "") +
        (ann.doctor_confirmed ? "" : " unconfirmed");
      card.dataset.id = ann.id;

      const rankClass = ann.rank ? "rank-badge-" + ann.rank : "rank-badge-manual";
      const rankLabel = ann.rank ? "Rank " + ann.rank : "手動";

      let findingsHtml = data.findingOptions.map(function (f) {
        const checked = (ann.findings || []).includes(f) ? "checked" : "";
        const label = data.findingLabels[f] || f;
        return '<label class="flex items-center gap-1 text-xs">' +
          '<input type="checkbox" class="finding-cb" data-finding="' + f + '" ' + checked + '>' +
          escapeHtml(label) + '</label>';
      }).join("");

      let labelOptions = data.labelOptions.map(function (l) {
        const sel = ann.label === l ? "selected" : "";
        return '<option value="' + l + '" ' + sel + '>' + l + '</option>';
      }).join("");

      const confText = ann.source === "manual"
        ? "手動追加"
        : (ann.ai_confidence != null ? (ann.ai_confidence * 100).toFixed(0) + "%" : "—");

      card.innerHTML =
        '<div class="flex items-center justify-between mb-2">' +
          '<span class="rank-badge ' + rankClass + ' px-2 py-0.5 rounded text-xs font-medium">' + rankLabel + '</span>' +
          '<div class="flex items-center gap-2">' +
            '<label class="text-xs flex items-center gap-1">' +
              '<input type="checkbox" class="confirmed-cb" ' + (ann.doctor_confirmed ? "checked" : "") + '> 採用' +
            '</label>' +
            '<button class="btn-delete text-red-500 text-xs hover:text-red-700">削除</button>' +
          '</div>' +
        '</div>' +
        '<div class="space-y-2">' +
          '<div><label class="text-xs font-medium">ラベル</label>' +
            '<select class="label-select w-full border rounded px-2 py-1 text-sm">' + labelOptions + '</select></div>' +
          '<div><label class="text-xs font-medium">所見タグ</label>' +
            '<div class="grid grid-cols-1 gap-1 mt-1">' + findingsHtml + '</div></div>' +
          '<div><label class="text-xs font-medium">AI信頼度</label>' +
            '<p class="text-sm text-slate-600">' + escapeHtml(confText) + '</p></div>' +
          '<div><label class="text-xs font-medium">理由</label>' +
            '<textarea class="reason-input w-full border rounded px-2 py-1 text-sm" rows="2">' +
              escapeHtml(ann.reason || "") + '</textarea></div>' +
          '<div><label class="text-xs font-medium">医師コメント</label>' +
            '<textarea class="comment-input w-full border rounded px-2 py-1 text-sm" rows="2">' +
              escapeHtml(ann.doctor_comment || "") + '</textarea></div>' +
        '</div>';

      card.addEventListener("click", function (e) {
        if (e.target.closest("button") || e.target.closest("input") || e.target.closest("select") || e.target.closest("textarea")) return;
        selectAnnotation(ann.id);
      });

      card.querySelector(".label-select").addEventListener("change", function (e) {
        patchAnnotation(ann.id, { label: e.target.value });
      });

      card.querySelectorAll(".finding-cb").forEach(function (cb) {
        cb.addEventListener("change", function () {
          const findings = [];
          card.querySelectorAll(".finding-cb:checked").forEach(function (c) {
            findings.push(c.dataset.finding);
          });
          patchAnnotation(ann.id, { findings: findings });
        });
      });

      card.querySelector(".reason-input").addEventListener("change", function (e) {
        patchAnnotation(ann.id, { reason: e.target.value });
      });

      card.querySelector(".comment-input").addEventListener("change", function (e) {
        patchAnnotation(ann.id, { doctor_comment: e.target.value });
      });

      card.querySelector(".confirmed-cb").addEventListener("change", function (e) {
        patchAnnotation(ann.id, { doctor_confirmed: e.target.checked });
      });

      card.querySelector(".btn-delete").addEventListener("click", function () {
        deleteAnnotation(ann.id);
      });

      annotationList.appendChild(card);
    });
  }

  function selectAnnotation(id) {
    selectedId = id;
    renderAnnotationList();
    drawCanvas();
  }

  function findAnn(id) {
    return annotations.find(function (a) { return a.id === id; });
  }

  async function patchAnnotation(id, fields) {
    hideError();
    try {
      const res = await fetch("/api/cases/" + data.caseId + "/annotations/" + id, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "更新に失敗しました");
      const idx = annotations.findIndex(function (a) { return a.id === id; });
      if (idx >= 0) annotations[idx] = body.annotation;
      renderAnnotationList();
      drawCanvas();
    } catch (err) {
      showError(err.message);
    }
  }

  async function deleteAnnotation(id) {
    if (!confirm("この候補点を削除しますか？")) return;
    hideError();
    try {
      const res = await fetch("/api/cases/" + data.caseId + "/annotations/" + id, {
        method: "DELETE",
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "削除に失敗しました");
      annotations = annotations.filter(function (a) { return a.id !== id; });
      if (selectedId === id) selectedId = null;
      renderAnnotationList();
      drawCanvas();
    } catch (err) {
      showError(err.message);
    }
  }

  async function addAnnotation(xRatio, yRatio) {
    hideError();
    try {
      const res = await fetch("/api/cases/" + data.caseId + "/annotations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          x_ratio: xRatio,
          y_ratio: yRatio,
          radius_ratio: 0.05,
          label: "LSIL_like",
          findings: [],
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "追加に失敗しました");
      annotations.push(body.annotation);
      selectedId = body.annotation.id;
      updateStatusBadge("ai_analyzed");
      renderAnnotationList();
      drawCanvas();
    } catch (err) {
      showError(err.message);
    }
  }

  canvas.addEventListener("mousedown", function (evt) {
    const { x, y } = canvasCoords(evt);

    if (addMode) {
      const xRatio = x / canvas.width;
      const yRatio = y / canvas.height;
      addAnnotation(xRatio, yRatio);
      return;
    }

    const hit = hitTest(x, y);
    if (hit) {
      selectedId = hit.ann.id;
      dragState = {
        annId: hit.ann.id,
        mode: hit.mode,
        startX: x,
        startY: y,
        origX: hit.ann.x_ratio,
        origY: hit.ann.y_ratio,
        origR: hit.ann.radius_ratio,
      };
      canvas.classList.add("mode-move");
      renderAnnotationList();
    } else {
      selectedId = null;
      renderAnnotationList();
      drawCanvas();
    }
  });

  canvas.addEventListener("mousemove", function (evt) {
    if (!dragState) return;
    const { x, y } = canvasCoords(evt);
    const ann = findAnn(dragState.annId);
    if (!ann) return;

    if (dragState.mode === "move") {
      ann.x_ratio = Math.max(0, Math.min(1, x / canvas.width));
      ann.y_ratio = Math.max(0, Math.min(1, y / canvas.height));
    } else {
      const cx = ann.x_ratio * canvas.width;
      const cy = ann.y_ratio * canvas.height;
      const newR = Math.hypot(x - cx, y - cy) / canvas.width;
      ann.radius_ratio = Math.max(MIN_RADIUS, newR);
    }
    drawCanvas();
  });

  function endDrag() {
    if (!dragState) return;
    const ann = findAnn(dragState.annId);
    canvas.classList.remove("mode-move");
    if (ann) {
      patchAnnotation(dragState.annId, {
        x_ratio: ann.x_ratio,
        y_ratio: ann.y_ratio,
        radius_ratio: ann.radius_ratio,
      });
    }
    dragState = null;
  }

  canvas.addEventListener("mouseup", endDrag);
  canvas.addEventListener("mouseleave", endDrag);

  document.getElementById("btn-add-mode").addEventListener("click", function () {
    addMode = !addMode;
    this.classList.toggle("bg-teal-100", addMode);
    this.classList.toggle("border-teal-500", addMode);
    canvas.style.cursor = addMode ? "crosshair" : "default";
  });

  document.getElementById("btn-analyze").addEventListener("click", async function () {
    hideError();
    loadingOverlay.classList.add("active");
    try {
      const res = await fetch("/api/cases/" + data.caseId + "/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: providerSelect.value }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "解析に失敗しました");
      annotations = body.annotations;
      updateStatusBadge(body.case.status);
      if (body.overall_comment) {
        overallComment.textContent = body.overall_comment;
        overallComment.classList.remove("hidden");
      }
      renderAnnotationList();
      drawCanvas();
    } catch (err) {
      showError(err.message);
    } finally {
      loadingOverlay.classList.remove("active");
    }
  });

  document.getElementById("btn-save-meta").addEventListener("click", async function () {
    hideError();
    try {
      const res = await fetch("/api/cases/" + data.caseId, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cytology_result: document.getElementById("cytology_result").value,
          hpv_result: document.getElementById("hpv_result").value,
          memo: document.getElementById("memo").value,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "保存に失敗しました");
      alert("症例情報を保存しました。");
    } catch (err) {
      showError(err.message);
    }
  });

  document.getElementById("btn-approve").addEventListener("click", async function () {
    hideError();
    if (!confirm("現在のアノテーション状態で承認して保存しますか？")) return;

    drawCanvas();
    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);

    try {
      const res = await fetch("/api/cases/" + data.caseId + "/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ annotated_image: dataUrl }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "承認に失敗しました");
      updateStatusBadge(body.case.status);
      alert("承認して保存しました。");
    } catch (err) {
      showError(err.message);
    }
  });

  function applyProviderStyle(provider) {
    providerSelect.classList.remove("provider-openai", "provider-anthropic", "provider-dummy");
    providerSelect.classList.add("provider-" + provider);
  }

  async function initProviderSelect() {
    try {
      const res = await fetch("/api/provider");
      const info = await res.json();
      providerSelect.value = info.provider;
      applyProviderStyle(info.provider);
    } catch (_) { /* ignore */ }

    providerSelect.addEventListener("change", async function () {
      const prev = providerSelect.dataset.prev || providerSelect.value;
      const provider = providerSelect.value;
      try {
        const res = await fetch("/api/provider/set", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: provider }),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || "プロバイダー切替に失敗しました");
        applyProviderStyle(provider);
        providerSelect.dataset.prev = provider;
      } catch (err) {
        alert(err.message);
        providerSelect.value = prev;
      }
    });
  }

  loadImage().then(function () {
    renderAnnotationList();
    initProviderSelect();
  }).catch(function () {
    showError("画像の読み込みに失敗しました。");
  });
})();
