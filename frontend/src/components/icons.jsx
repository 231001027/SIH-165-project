/**
 * Small, hand-authored outline icon set (no external icon-library dependency
 * -- keeps the app fully offline-installable, consistent with the project's
 * "runs without external services" design goal). One consistent visual
 * language: 1.75 stroke, rounded joins, 24x24 viewbox.
 */
const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function S({ children, className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...base}>
      {children}
    </svg>
  );
}

export const IconGrid = (p) => (
  <S {...p}>
    <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
    <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
    <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
  </S>
);

export const IconList = (p) => (
  <S {...p}>
    <path d="M8 6h13M8 12h13M8 18h13" />
    <path d="M3 6h.01M3 12h.01M3 18h.01" />
  </S>
);

export const IconPlus = (p) => (
  <S {...p}>
    <path d="M12 5v14M5 12h14" />
  </S>
);

export const IconUpload = (p) => (
  <S {...p}>
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </S>
);

export const IconCheckShield = (p) => (
  <S {...p}>
    <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
    <path d="M9 12l2 2 4-4" />
  </S>
);

export const IconCluster = (p) => (
  <S {...p}>
    <circle cx="6" cy="7" r="2.4" />
    <circle cx="17" cy="6" r="2" />
    <circle cx="15" cy="16" r="2.6" />
    <circle cx="6" cy="16" r="1.7" />
    <path d="M8 8l5 6M8.5 7.5l6.5-1M7 15l6.3-.7" opacity="0.6" />
  </S>
);

export const IconTrend = (p) => (
  <S {...p}>
    <path d="M3 17l6-6 4 4 8-9" />
    <path d="M15 6h6v6" />
  </S>
);

export const IconRank = (p) => (
  <S {...p}>
    <path d="M4 20V10M12 20V4M20 20v-7" />
  </S>
);

export const IconEval = (p) => (
  <S {...p}>
    <rect x="4" y="3.5" width="16" height="17" rx="2" />
    <path d="M8.5 8.5h7M8.5 12h7M8.5 15.5h4.5" />
  </S>
);

export const IconLock = (p) => (
  <S {...p}>
    <rect x="5" y="10.5" width="14" height="9.5" rx="2" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
  </S>
);

export const IconInfo = (p) => (
  <S {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5.2M12 8.3h.01" />
  </S>
);

export const IconLogout = (p) => (
  <S {...p}>
    <path d="M9 20H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3" />
    <path d="M16 17l5-5-5-5M21 12H9" />
  </S>
);

export const IconChevronRight = (p) => (
  <S {...p}>
    <path d="M9 6l6 6-6 6" />
  </S>
);

export const IconChevronDown = (p) => (
  <S {...p}>
    <path d="M6 9l6 6 6-6" />
  </S>
);

export const IconArrowLeft = (p) => (
  <S {...p}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </S>
);

export const IconExternal = (p) => (
  <S {...p}>
    <path d="M14 4h6v6" />
    <path d="M20 4L10 14" />
    <path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" />
  </S>
);

export const IconAlertTriangle = (p) => (
  <S {...p}>
    <path d="M12 4l9.5 16.5H2.5z" />
    <path d="M12 10v4.2M12 17.2h.01" />
  </S>
);

export const IconFlame = (p) => (
  <S {...p}>
    <path d="M12 2.5c1.2 3 4.5 4.6 4.5 8.6a4.5 4.5 0 1 1-9 0c0-1.3.5-2.2 1.1-3.1.3.9 1 1.4 1.7 1.2C9.6 7 8.8 5 12 2.5z" />
  </S>
);

export const IconBolt = (p) => (
  <S {...p}>
    <path d="M13 2L4 14h6l-1 8 9-12h-6z" />
  </S>
);

export const IconDrop = (p) => (
  <S {...p}>
    <path d="M12 2.5S5.5 10 5.5 14.7a6.5 6.5 0 0 0 13 0C18.5 10 12 2.5 12 2.5z" />
  </S>
);

export const IconArrowUpRight = (p) => (
  <S {...p}>
    <path d="M7 17L17 7M9 7h8v8" />
  </S>
);

export const IconArrowDownRight = (p) => (
  <S {...p}>
    <path d="M7 7l10 10M17 7v10H7" />
  </S>
);

export const IconSearch = (p) => (
  <S {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </S>
);

export const IconFilter = (p) => (
  <S {...p}>
    <path d="M4 5h16M7 12h10M10.5 19h3" />
  </S>
);

export const IconX = (p) => (
  <S {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </S>
);

export const IconLink = (p) => (
  <S {...p}>
    <path d="M9.5 14.5l5-5" />
    <path d="M11 6.5l.8-.8a3.5 3.5 0 1 1 5 5l-.8.8M13 17.5l-.8.8a3.5 3.5 0 1 1-5-5l.8-.8" />
  </S>
);

export const IconLayers = (p) => (
  <S {...p}>
    <path d="M12 3l8.5 4.5L12 12 3.5 7.5z" />
    <path d="M3.5 12.5L12 17l8.5-4.5" />
    <path d="M3.5 16.5L12 21l8.5-4.5" />
  </S>
);

export const IconBook = (p) => (
  <S {...p}>
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z" />
    <path d="M4 5.5v15" />
  </S>
);

export const IconClock = (p) => (
  <S {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </S>
);

export const IconSparkle = (p) => (
  <S {...p}>
    <path d="M12 3l1.4 4.6L18 9l-4.6 1.4L12 15l-1.4-4.6L6 9l4.6-1.4z" />
    <path d="M19 15l.7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7z" />
  </S>
);

export const IconMapPin = (p) => (
  <S {...p}>
    <path d="M12 21s7-6.6 7-11.5A7 7 0 0 0 5 9.5C5 14.4 12 21 12 21z" />
    <circle cx="12" cy="9.5" r="2.3" />
  </S>
);
