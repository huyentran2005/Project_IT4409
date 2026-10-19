import type { UserSummary } from '../../types/task'

export function Avatar({ user, size = 30 }: { user: UserSummary; size?: number }) {
  return (
    <span className="avatar" title={user.name} style={{ width: size, height: size, background: user.color }}>
      {user.initials}
    </span>
  )
}
