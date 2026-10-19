import { Icon } from '../ui/Icon'
import { mockNavigation } from '../../data/mockData'
import type { ProjectSummary } from '../../types/task'

interface AppSidebarProps {
  open: boolean
  activeSection: string
  activeProjectId: string
  projects: ProjectSummary[]
  onNavigate: (label: string) => void
  onSelectProject: (projectId: string) => void
  onCreateProject: () => void
  onToggleHidden: () => void
  onClose: () => void
}

export function AppSidebar({ open, activeSection, activeProjectId, projects, onNavigate, onSelectProject, onCreateProject, onToggleHidden, onClose }: AppSidebarProps) {
  return (
    <>
      <aside className={`sidebar ${open ? 'sidebar--open' : ''}`}>
        <div className="brand">
          <span className="brand__mark"><span /><span /><span /></span>
          <span className="brand__name">TaskFlow</span>
          <button className="sidebar-toggle" onClick={onToggleHidden} aria-label="Ẩn thanh bên" title="Ẩn thanh bên"><Icon name="chevron" size={17} /></button>
        </div>

        <nav className="sidebar__nav" aria-label="Điều hướng chính">
          <div className="nav-group">
            {mockNavigation.map((link) => (
              <button className={`nav-item ${activeSection === link.label ? 'nav-item--active' : ''}`} onClick={() => onNavigate(link.label)} key={link.label}>
                <Icon name={link.icon} size={19} />
                <span>{link.label}</span>
                {link.badge && <span className="nav-item__badge">{link.badge}</span>}
              </button>
            ))}
          </div>

          <div className="nav-section">
            <div className="nav-section__heading">
              <span>Dự án</span>
              <button onClick={onCreateProject} aria-label="Tạo dự án"><Icon name="plus" size={16} /></button>
            </div>
            {projects.map((project) => (
              <button className={`project-link ${activeSection === 'Dự án' && activeProjectId === project.id ? 'project-link--active' : ''}`} onClick={() => { onSelectProject(project.id); onNavigate('Dự án') }} key={project.id}>
                <span className="project-dot" style={{ background: project.color }} />
                <span>{project.name}</span>
              </button>
            ))}
          </div>
        </nav>

        <div className="sidebar__footer">
          <div className="help-card">
            <span className="help-card__icon">?</span>
            <div><strong>Cần trợ giúp?</strong><small>Xem hướng dẫn sử dụng</small></div>
            <Icon name="chevron" size={15} />
          </div>
        </div>
      </aside>
      {open && <button className="sidebar-scrim" aria-label="Đóng menu" onClick={onClose} />}
    </>
  )
}
