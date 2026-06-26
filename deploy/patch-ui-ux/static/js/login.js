(function () {
  var STORAGE_USERNAMES = "maxek_saved_usernames";
  var MAX_USERNAMES = 12;

  function loadUsernames() {
    try {
      var raw = localStorage.getItem(STORAGE_USERNAMES);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list.filter(Boolean) : [];
    } catch (e) {
      return [];
    }
  }

  function saveUsername(name) {
    if (!name) return;
    var list = loadUsernames().filter(function (u) {
      return u.toLowerCase() !== name.toLowerCase();
    });
    list.unshift(name);
    localStorage.setItem(STORAGE_USERNAMES, JSON.stringify(list.slice(0, MAX_USERNAMES)));
  }

  function initPasswordToggle() {
    var field = document.querySelector(".login-field-password");
    if (!field) return;
    var input = field.querySelector('input[type="password"], input[name="password"]');
    var btn = field.querySelector("[data-toggle-password]");
    if (!input || !btn) return;
    btn.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
      btn.querySelector("i")?.classList.toggle("fa-eye", !show);
      btn.querySelector("i")?.classList.toggle("fa-eye-slash", show);
    });
  }

  function initUsernameAutocomplete() {
    var input = document.querySelector('input[name="username"]');
    var datalist = document.getElementById("login-usernames");
    if (!input || !datalist) return;
    var names = loadUsernames();
    datalist.innerHTML = "";
    names.forEach(function (name) {
      var opt = document.createElement("option");
      opt.value = name;
      datalist.appendChild(opt);
    });
    var remembered = input.getAttribute("data-remembered-user");
    if (remembered && !input.value) {
      input.value = remembered;
    }
  }

  function initFormSubmit() {
    var form = document.querySelector(".login-form");
    if (!form) return;
    form.addEventListener("submit", function () {
      var username = form.querySelector('input[name="username"]');
      if (username && username.value.trim()) {
        saveUsername(username.value.trim());
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initPasswordToggle();
    initUsernameAutocomplete();
    initFormSubmit();
  });
})();
