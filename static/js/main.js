const sidebar = document.getElementById('sidebar');
const backdrop = document.getElementById('sidebarBackdrop');
function toggleSidebar() {
  sidebar?.classList.toggle('open');
  backdrop?.classList.toggle('open');
  document.getElementById('menuToggle')?.setAttribute('aria-expanded', String(sidebar?.classList.contains('open')));
}
document.getElementById('menuToggle')?.addEventListener('click', toggleSidebar);
backdrop?.addEventListener('click', toggleSidebar);
document.addEventListener('keydown', event => { if (event.key === 'Escape' && sidebar?.classList.contains('open')) toggleSidebar(); });
document.getElementById('deleteModal')?.addEventListener('show.bs.modal', event => {
  const target = event.relatedTarget?.dataset.deleteUrl;
  if (target) document.getElementById('deleteForm').action = target;
});
document.querySelectorAll('.page-link-control').forEach(link => {
  const url = new URL(window.location.href);
  url.searchParams.set('page', link.dataset.page);
  link.href = url.toString();
});
