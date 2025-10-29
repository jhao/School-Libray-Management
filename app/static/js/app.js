(function() {
  var toggleButton = document.getElementById('mobile-menu-toggle');
  if (!toggleButton) {
    return;
  }

  toggleButton.addEventListener('click', function() {
    if (document.body.classList.contains('sidebar-open')) {
      document.body.classList.remove('sidebar-open');
    } else {
      document.body.classList.add('sidebar-open');
    }
  });

  document.addEventListener('click', function(event) {
    if (!document.body.classList.contains('sidebar-open')) {
      return;
    }
    var sidebar = document.getElementById('app-sidebar');
    if (!sidebar.contains(event.target) && event.target !== toggleButton) {
      document.body.classList.remove('sidebar-open');
    }
  });
})();
