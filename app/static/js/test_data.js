(function() {
  var form = document.getElementById('test-data-form');
  if (!form) {
    return;
  }

  var startInput = document.getElementById('start-date');
  var endInput = document.getElementById('end-date');
  var countInput = document.getElementById('record-count');
  var returnRateInput = document.getElementById('return-rate');
  var excludeContainer = document.getElementById('exclude-tags');
  var manualInput = document.getElementById('manual-exclude');
  var addExcludeButton = document.getElementById('add-exclude');
  var resetButton = document.getElementById('reset-form');
  var progressWrapper = document.getElementById('progress-wrapper');
  var progressBar = document.getElementById('progress-bar');
  var progressText = document.getElementById('progress-text');
  var statusMessage = document.getElementById('status-message');

  var weekendSet = new Set();
  var manualSet = new Set();

  function formatDate(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, '0');
    var day = String(date.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  function calculateWeekendSet() {
    weekendSet.clear();
    var startValue = startInput.value;
    var endValue = endInput.value;
    if (!startValue || !endValue) {
      renderTags();
      return;
    }
    var startDate = new Date(startValue);
    var endDate = new Date(endValue);
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime()) || startDate > endDate) {
      renderTags();
      return;
    }
    var cursor = new Date(startDate);
    while (cursor <= endDate) {
      if (cursor.getDay() === 0 || cursor.getDay() === 6) {
        weekendSet.add(formatDate(cursor));
      }
      cursor.setDate(cursor.getDate() + 1);
    }
    renderTags();
  }

  function renderTags() {
    if (!excludeContainer) {
      return;
    }
    excludeContainer.innerHTML = '';
    var allDates = Array.from(new Set([].concat(Array.from(weekendSet), Array.from(manualSet))));
    allDates.sort();
    if (!allDates.length) {
      var empty = document.createElement('span');
      empty.className = 'text-muted';
      empty.textContent = '当前未排除任何日期';
      excludeContainer.appendChild(empty);
      return;
    }
    allDates.forEach(function(date) {
      var tag = document.createElement('span');
      var isWeekend = weekendSet.has(date);
      tag.className = 'exclude-tag' + (isWeekend ? ' weekend' : '');
      tag.textContent = date;
      var closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'exclude-tag-remove';
      closeBtn.innerHTML = '&times;';
      closeBtn.addEventListener('click', function() {
        if (isWeekend) {
          weekendSet.delete(date);
        } else {
          manualSet.delete(date);
        }
        renderTags();
      });
      tag.appendChild(closeBtn);
      excludeContainer.appendChild(tag);
    });
  }

  function addManualDate(dateValue) {
    if (!dateValue) {
      return;
    }
    manualSet.add(dateValue);
    renderTags();
  }

  function setFormDisabled(disabled) {
    Array.prototype.forEach.call(form.elements, function(el) {
      el.disabled = disabled;
    });
    if (disabled) {
      manualInput.disabled = true;
      addExcludeButton.disabled = true;
    } else {
      manualInput.disabled = false;
      addExcludeButton.disabled = false;
    }
  }

  function showProgress(total, current) {
    if (!progressWrapper || !progressBar || !progressText) {
      return;
    }
    if (progressWrapper.classList.contains('hidden')) {
      progressWrapper.classList.remove('hidden');
    }
    var percent = total ? Math.round((current / total) * 100) : 0;
    percent = Math.min(100, Math.max(0, percent));
    progressBar.style.width = percent + '%';
    progressBar.textContent = percent + '%';
    progressBar.setAttribute('aria-valuenow', percent);
    progressText.textContent = '正在生成：' + current + ' / ' + total;
  }

  function hideProgress() {
    if (progressWrapper) {
      progressWrapper.classList.add('hidden');
    }
    if (progressBar) {
      progressBar.style.width = '0%';
      progressBar.textContent = '0%';
      progressBar.setAttribute('aria-valuenow', '0');
    }
    if (progressText) {
      progressText.textContent = '准备中...';
    }
  }

  function showStatus(message, type) {
    if (!statusMessage) {
      return;
    }
    statusMessage.textContent = message;
    statusMessage.className = 'alert alert-' + (type || 'info');
    statusMessage.classList.remove('hidden');
  }

  function hideStatus() {
    if (statusMessage) {
      statusMessage.className = 'alert alert-info hidden';
      statusMessage.textContent = '';
    }
  }

  function gatherSelectedIds(selector, attribute) {
    return Array.prototype.slice.call(document.querySelectorAll(selector)).filter(function(input) {
      return input.checked;
    }).map(function(input) {
      return parseInt(input.getAttribute(attribute), 10);
    }).filter(function(value) {
      return !isNaN(value);
    });
  }

  function toggleGradeWithClasses(gradeId, checked) {
    var classBoxes = document.querySelectorAll('.class-checkbox[data-grade-id="' + gradeId + '"]');
    Array.prototype.forEach.call(classBoxes, function(box) {
      box.checked = checked;
    });
  }

  function syncGradeFromClasses(gradeId) {
    var gradeBox = document.querySelector('.grade-checkbox[data-grade-id="' + gradeId + '"]');
    if (!gradeBox) {
      return;
    }
    var classBoxes = document.querySelectorAll('.class-checkbox[data-grade-id="' + gradeId + '"]');
    if (!classBoxes.length) {
      return;
    }
    var allChecked = Array.prototype.every.call(classBoxes, function(box) {
      return box.checked;
    });
    gradeBox.checked = allChecked;
  }

  document.querySelectorAll('.grade-checkbox').forEach(function(checkbox) {
    checkbox.addEventListener('change', function() {
      toggleGradeWithClasses(checkbox.getAttribute('data-grade-id'), checkbox.checked);
    });
  });

  document.querySelectorAll('.class-checkbox').forEach(function(checkbox) {
    checkbox.addEventListener('change', function() {
      syncGradeFromClasses(checkbox.getAttribute('data-grade-id'));
    });
  });

  if (addExcludeButton) {
    addExcludeButton.addEventListener('click', function() {
      if (!manualInput.value) {
        return;
      }
      addManualDate(manualInput.value);
      manualInput.value = '';
    });
  }

  if (manualInput) {
    manualInput.addEventListener('keydown', function(event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        if (manualInput.value) {
          addManualDate(manualInput.value);
          manualInput.value = '';
        }
      }
    });
  }

  if (resetButton) {
    resetButton.addEventListener('click', function() {
      form.reset();
      weekendSet.clear();
      manualSet.clear();
      hideProgress();
      hideStatus();
      calculateWeekendSet();
    });
  }

  if (startInput) {
    startInput.addEventListener('change', calculateWeekendSet);
  }
  if (endInput) {
    endInput.addEventListener('change', calculateWeekendSet);
  }

  calculateWeekendSet();

  async function sendGenerationRequest(payload) {
    var response = await fetch(form.getAttribute('data-execute-endpoint'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      var message = '服务器返回错误';
      try {
        var errorData = await response.json();
        if (errorData && errorData.message) {
          message = errorData.message;
        }
      } catch (err) {
        // ignore
      }
      throw new Error(message);
    }
    var data = await response.json();
    if (!data.success) {
      throw new Error(data.message || '生成失败');
    }
    return data;
  }

  async function logBatch(payload) {
    var response = await fetch(form.getAttribute('data-log-endpoint'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      return false;
    }
    var data = await response.json();
    return !!data.success;
  }

  if (form) {
    form.setAttribute('data-execute-endpoint', form.getAttribute('data-execute-endpoint') || form.dataset.executeEndpoint || window.executeTestDataEndpoint || '/system/test-data/execute');
    form.setAttribute('data-log-endpoint', form.getAttribute('data-log-endpoint') || form.dataset.logEndpoint || window.logTestDataEndpoint || '/system/test-data/batches');
  }

  form.addEventListener('submit', async function(event) {
    event.preventDefault();
    hideStatus();

    var startDate = startInput.value;
    var endDate = endInput.value;
    var count = parseInt(countInput.value, 10);
    if (!startDate || !endDate) {
      showStatus('请选择开始和结束日期。', 'warning');
      return;
    }
    if (isNaN(count) || count <= 0) {
      showStatus('请填写有效的生成数量。', 'warning');
      return;
    }
    if (new Date(startDate) > new Date(endDate)) {
      showStatus('开始日期不能晚于结束日期。', 'warning');
      return;
    }

    var payloadBase = {
      start_date: startDate,
      end_date: endDate,
      excluded_dates: Array.from(new Set([].concat(Array.from(weekendSet), Array.from(manualSet)))),
      grade_ids: gatherSelectedIds('.grade-checkbox', 'data-grade-id'),
      class_ids: gatherSelectedIds('.class-checkbox', 'data-class-id'),
      return_rate: parseFloat(returnRateInput.value || '0.7')
    };

    setFormDisabled(true);
    showProgress(count, 0);

    try {
      for (var index = 0; index < count; index += 1) {
        await sendGenerationRequest(payloadBase);
        showProgress(count, index + 1);
      }
      var logged = await logBatch(Object.assign({ record_count: count }, payloadBase));
      if (logged) {
        showStatus('测试数据生成完成，即将刷新页面。', 'success');
        setTimeout(function() {
          window.location.reload();
        }, 1200);
      } else {
        showStatus('数据生成完成，但记录保存失败，请手动刷新查看。', 'warning');
      }
    } catch (error) {
      showStatus(error.message || '生成过程中出现错误。', 'danger');
    } finally {
      setFormDisabled(false);
      hideProgress();
    }
  });
})();
