interface TeacherMascotProps {
  className?: string;
  title?: string;
}

export default function TeacherMascot({
  className,
  title = 'AI 교사',
}: TeacherMascotProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <defs>
        <linearGradient id="teacher-face" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFE0B2" />
          <stop offset="100%" stopColor="#FFCC80" />
        </linearGradient>
        <linearGradient id="teacher-hair" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#5D4037" />
          <stop offset="100%" stopColor="#3E2723" />
        </linearGradient>
      </defs>

      {/* book under chin */}
      <rect x="14" y="48" width="36" height="10" rx="2" fill="#1E88E5" />
      <rect x="14" y="48" width="36" height="3" fill="#1565C0" />
      <line
        x1="32"
        y1="48"
        x2="32"
        y2="58"
        stroke="#FFFFFF"
        strokeWidth="1.2"
        opacity="0.8"
      />

      {/* neck */}
      <rect x="27" y="42" width="10" height="8" rx="2" fill="url(#teacher-face)" />

      {/* face */}
      <circle cx="32" cy="28" r="18" fill="url(#teacher-face)" />

      {/* hair */}
      <path
        d="M14 28 Q14 10 32 10 Q50 10 50 28 L50 22 Q42 16 32 16 Q22 16 14 22 Z"
        fill="url(#teacher-hair)"
      />

      {/* ears */}
      <circle cx="14" cy="30" r="3" fill="url(#teacher-face)" />
      <circle cx="50" cy="30" r="3" fill="url(#teacher-face)" />

      {/* glasses */}
      <circle
        cx="25"
        cy="30"
        r="5"
        fill="none"
        stroke="#37474F"
        strokeWidth="1.6"
      />
      <circle
        cx="39"
        cy="30"
        r="5"
        fill="none"
        stroke="#37474F"
        strokeWidth="1.6"
      />
      <line x1="30" y1="30" x2="34" y2="30" stroke="#37474F" strokeWidth="1.6" />

      {/* eyes */}
      <circle cx="25" cy="30" r="1.6" fill="#1B1B1B" />
      <circle cx="39" cy="30" r="1.6" fill="#1B1B1B" />
      <circle cx="25.6" cy="29.4" r="0.5" fill="#FFFFFF" />
      <circle cx="39.6" cy="29.4" r="0.5" fill="#FFFFFF" />

      {/* smile */}
      <path
        d="M27 38 Q32 42 37 38"
        fill="none"
        stroke="#5D4037"
        strokeWidth="1.6"
        strokeLinecap="round"
      />

      {/* cheek blush */}
      <circle cx="21" cy="36" r="2" fill="#FFAB91" opacity="0.55" />
      <circle cx="43" cy="36" r="2" fill="#FFAB91" opacity="0.55" />
    </svg>
  );
}
