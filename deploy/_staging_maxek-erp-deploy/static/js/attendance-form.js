(function () {
  function syncHasValue(field) {
    if (!field) return;
    field.classList.toggle('has-value', field.value !== '');
  }

  function getSelectedWorkerOption(nameSelect, idSelect) {
    var source = nameSelect && nameSelect.value ? nameSelect : idSelect;
    if (!source || !source.value) return null;
    return source.options[source.selectedIndex];
  }

  function setRowVisible(row, visible) {
    if (!row) return;
    row.hidden = !visible;
  }

  function initAttendanceForm() {
    var form = document.querySelector('[data-attendance-form]');
    if (!form) return;

    var staffType = form.querySelector('#attendance_staff_type');
    var companyNameRow = form.querySelector('#attendance_company_worker_name_row');
    var companyIdRow = form.querySelector('#attendance_company_worker_id_row');
    var subNameRow = form.querySelector('#attendance_subcontractor_name_row');
    var subIdRow = form.querySelector('#attendance_subcontractor_id_row');
    var subWorkerNameRow = form.querySelector('#attendance_sub_worker_name_row');
    var subWorkerIdRow = form.querySelector('#attendance_sub_worker_id_row');
    var companyWorkerName = form.querySelector('#attendance_company_worker_name');
    var companyWorkerId = form.querySelector('#attendance_company_worker_id');
    var subcontractorName = form.querySelector('#attendance_subcontractor_name');
    var subcontractorId = form.querySelector('#attendance_subcontractor_id');
    var subWorkerName = form.querySelector('#attendance_sub_worker_name');
    var subWorkerId = form.querySelector('#attendance_sub_worker_id');
    var workerRef = form.querySelector('#attendance_worker_ref');
    var projectNumber = form.querySelector('#attendance_project_number');
    var projectName = form.querySelector('#attendance_project_name');
    var verifyPanel = form.querySelector('#attendance_worker_verify');
    var photoImg = form.querySelector('#attendance_worker_photo');
    var photoEmpty = form.querySelector('#attendance_worker_photo_empty');
    var verifyName = form.querySelector('#attendance_worker_verify_name');
    var verifyCode = form.querySelector('#attendance_worker_verify_code');
    var photosBase = form.getAttribute('data-photos-base') || '/static/photos/';

    function activeWorkerSelects() {
      if (staffType && staffType.value === 'Sub Contractor Staff') {
        return { nameSelect: subWorkerName, idSelect: subWorkerId };
      }
      if (staffType && staffType.value === 'Company Staff') {
        return { nameSelect: companyWorkerName, idSelect: companyWorkerId };
      }
      return { nameSelect: null, idSelect: null };
    }

    function syncWorkerRef() {
      var active = activeWorkerSelects();
      var value = '';
      if (active.nameSelect && active.nameSelect.value) {
        value = active.nameSelect.value;
      } else if (active.idSelect && active.idSelect.value) {
        value = active.idSelect.value;
      }
      if (workerRef) workerRef.value = value;
    }

    function updateWorkerPhoto() {
      var active = activeWorkerSelects();
      var option = getSelectedWorkerOption(active.nameSelect, active.idSelect);
      if (!option || !option.value) {
        if (verifyPanel) verifyPanel.hidden = true;
        syncWorkerRef();
        return;
      }

      var label = option.getAttribute('data-worker-label') || option.textContent.trim();
      var code = option.getAttribute('data-worker-code') || '';
      var photoFile = option.getAttribute('data-worker-photo') || '';

      if (verifyPanel) verifyPanel.hidden = false;
      if (verifyName) verifyName.textContent = label;
      if (verifyCode) verifyCode.textContent = code ? 'ID: ' + code : '';

      if (photoFile && photoImg) {
        photoImg.src = photosBase + photoFile;
        photoImg.alt = label + ' photo';
        photoImg.hidden = false;
        if (photoEmpty) photoEmpty.hidden = true;
      } else {
        if (photoImg) {
          photoImg.removeAttribute('src');
          photoImg.hidden = true;
        }
        if (photoEmpty) photoEmpty.hidden = false;
      }
      syncWorkerRef();
    }

    function syncCompanyWorkerFromName() {
      if (!companyWorkerName || !companyWorkerId) return;
      companyWorkerId.value = companyWorkerName.value;
      syncHasValue(companyWorkerId);
      updateWorkerPhoto();
    }

    function syncCompanyWorkerFromId() {
      if (!companyWorkerName || !companyWorkerId) return;
      companyWorkerName.value = companyWorkerId.value;
      syncHasValue(companyWorkerName);
      updateWorkerPhoto();
    }

    function syncSubcontractorFromName() {
      if (!subcontractorName || !subcontractorId) return;
      subcontractorId.value = subcontractorName.value;
      syncHasValue(subcontractorId);
      filterSubcontractorWorkers();
    }

    function syncSubcontractorFromId() {
      if (!subcontractorName || !subcontractorId) return;
      subcontractorName.value = subcontractorId.value;
      syncHasValue(subcontractorName);
      filterSubcontractorWorkers();
    }

    function syncSubWorkerFromName() {
      if (!subWorkerName || !subWorkerId) return;
      subWorkerId.value = subWorkerName.value;
      syncHasValue(subWorkerId);
      updateWorkerPhoto();
    }

    function syncSubWorkerFromId() {
      if (!subWorkerName || !subWorkerId) return;
      subWorkerName.value = subWorkerId.value;
      syncHasValue(subWorkerName);
      updateWorkerPhoto();
    }

    function filterSubcontractorWorkers() {
      var selectedSubId = subcontractorName ? subcontractorName.value : '';
      var hasSub = !!selectedSubId;

      [subWorkerName, subWorkerId].forEach(function (select) {
        if (!select) return;
        Array.prototype.forEach.call(select.options, function (option, index) {
          if (index === 0) {
            option.hidden = false;
            return;
          }
          var subId = option.getAttribute('data-subcontractor-id') || '';
          var matches = hasSub && subId === selectedSubId;
          option.hidden = !matches;
          if (!matches && option.selected) {
            option.selected = false;
          }
        });
        if (!hasSub) {
          select.value = '';
        } else if (select.value) {
          var current = select.options[select.selectedIndex];
          if (!current || current.hidden) {
            select.value = '';
          }
        }
        syncHasValue(select);
      });

      setRowVisible(subWorkerNameRow, hasSub);
      setRowVisible(subWorkerIdRow, hasSub);
      updateWorkerPhoto();
    }

    function clearCompanyWorkerSelection() {
      if (companyWorkerName) {
        companyWorkerName.value = '';
        syncHasValue(companyWorkerName);
      }
      if (companyWorkerId) {
        companyWorkerId.value = '';
        syncHasValue(companyWorkerId);
      }
    }

    function clearSubcontractorSelection() {
      if (subcontractorName) {
        subcontractorName.value = '';
        syncHasValue(subcontractorName);
      }
      if (subcontractorId) {
        subcontractorId.value = '';
        syncHasValue(subcontractorId);
      }
      if (subWorkerName) {
        subWorkerName.value = '';
        syncHasValue(subWorkerName);
      }
      if (subWorkerId) {
        subWorkerId.value = '';
        syncHasValue(subWorkerId);
      }
    }

    function toggleStaffTypeSections() {
      var type = staffType ? staffType.value : '';
      var isCompany = type === 'Company Staff';
      var isSub = type === 'Sub Contractor Staff';

      setRowVisible(companyNameRow, isCompany);
      setRowVisible(companyIdRow, isCompany);
      setRowVisible(subNameRow, isSub);
      setRowVisible(subIdRow, isSub);
      setRowVisible(subWorkerNameRow, isSub && subcontractorName && !!subcontractorName.value);
      setRowVisible(subWorkerIdRow, isSub && subcontractorName && !!subcontractorName.value);

      if (!isCompany) clearCompanyWorkerSelection();
      if (!isSub) clearSubcontractorSelection();
      if (isSub) filterSubcontractorWorkers();

      if (verifyPanel && !isCompany && !isSub) verifyPanel.hidden = true;
      updateWorkerPhoto();
    }

    function syncProjectFromNumber() {
      if (!projectNumber || !projectName) return;
      projectName.value = projectNumber.value;
      syncHasValue(projectName);
    }

    function syncProjectFromName() {
      if (!projectNumber || !projectName) return;
      projectNumber.value = projectName.value;
      syncHasValue(projectNumber);
    }

    if (staffType) {
      staffType.addEventListener('change', toggleStaffTypeSections);
    }
    if (companyWorkerName) {
      companyWorkerName.addEventListener('change', syncCompanyWorkerFromName);
    }
    if (companyWorkerId) {
      companyWorkerId.addEventListener('change', syncCompanyWorkerFromId);
    }
    if (subcontractorName) {
      subcontractorName.addEventListener('change', syncSubcontractorFromName);
    }
    if (subcontractorId) {
      subcontractorId.addEventListener('change', syncSubcontractorFromId);
    }
    if (subWorkerName) {
      subWorkerName.addEventListener('change', syncSubWorkerFromName);
    }
    if (subWorkerId) {
      subWorkerId.addEventListener('change', syncSubWorkerFromId);
    }
    if (projectNumber) {
      projectNumber.addEventListener('change', syncProjectFromNumber);
    }
    if (projectName) {
      projectName.addEventListener('change', syncProjectFromName);
    }

    form.addEventListener('submit', function (event) {
      syncWorkerRef();
      if (!workerRef || !workerRef.value) {
        event.preventDefault();
        window.alert('Select a worker before saving attendance.');
      }
    });

    var editWorkerRef = form.getAttribute('data-edit-worker-ref') || '';
    var editStaffType = form.getAttribute('data-edit-staff-type') || '';
    var editSubcontractorId = form.getAttribute('data-edit-subcontractor-id') || '';

    if (editStaffType && staffType) {
      staffType.value = editStaffType;
      syncHasValue(staffType);
      toggleStaffTypeSections();
      if (editStaffType === 'Company Staff' && editWorkerRef) {
        if (companyWorkerName) companyWorkerName.value = editWorkerRef;
        syncCompanyWorkerFromName();
      } else if (editStaffType === 'Sub Contractor Staff') {
        if (subcontractorName && editSubcontractorId) {
          subcontractorName.value = editSubcontractorId;
          syncSubcontractorFromName();
        }
        if (subWorkerName && editWorkerRef) {
          subWorkerName.value = editWorkerRef;
          syncSubWorkerFromName();
        }
      }
    } else if (staffType && staffType.value) {
      toggleStaffTypeSections();
    }

    if (projectName && projectName.value) {
      syncProjectFromName();
    } else if (projectNumber && projectNumber.value) {
      syncProjectFromNumber();
    }
  }

  document.addEventListener('DOMContentLoaded', initAttendanceForm);
})();
