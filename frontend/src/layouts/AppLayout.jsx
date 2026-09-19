import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  IconGrid, IconList, IconPlus, IconUpload, IconCheckShield, IconCluster,
  IconTrend, IconRank, IconEval, IconLock, IconInfo, IconLogout,
} from "../components/icons";

const NAV_SECTIONS = [
  {
    label: "Overview",
    items: [{ to: "/dashboard", label: "Dashboard", icon: IconGrid }],
  },
  {
    label: "Reports",
    items: [
      { to: "/reports", label: "All Reports", icon: IconList, end: true },
      { to: "/reports/new", label: "New Report", icon: IconPlus },
      { to: "/upload", label: "CSV Upload", icon: IconUpload },
      { to: "/review", label: "Review Queue", icon: IconCheckShield },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/clusters", label: "Precursor Clusters", icon: IconCluster },
      { to: "/trends", label: "Trends", icon: IconTrend },
      { to: "/rankings", label: "Site / Activity Ranking", icon: IconRank },
      { to: "/evaluation", label: "Evaluation", icon: IconEval },
    ],
  },
];

function NavItem({ to, label, icon: Icon, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-semibold transition ${
          isActive ? "bg-white/[0.08] text-white" : "text-ink-500 hover:bg-white/[0.05] hover:text-white/90"
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r bg-accent-500" />}
          <Icon className={`h-[18px] w-[18px] flex-shrink-0 ${isActive ? "text-accent-400" : ""}`} />
          {label}
        </>
      )}
    </NavLink>
  );
}

export default function AppLayout() {
  const { user, logout, hasRole } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const currentLabel =
    [...NAV_SECTIONS.flatMap((s) => s.items), { to: "/audit", label: "Audit Trail" }, { to: "/about", label: "About / LSR Reference" }]
      .find((i) => (i.to === "/reports" ? location.pathname === "/reports" : location.pathname.startsWith(i.to)))?.label || "";

  return (
    <div className="flex min-h-screen bg-surface">
      <aside className="bg-grain relative flex w-[248px] flex-shrink-0 flex-col bg-ink-950 text-white">
        <div className="relative border-b border-white/[0.08] px-5 py-5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 text-[13px] font-extrabold text-ink-950 shadow-glow">
              SG
            </span>
            <div>
              <p className="text-[14.5px] font-extrabold leading-tight tracking-tight">SIFGuard-OIL</p>
              <p className="text-[10px] font-medium uppercase tracking-wide text-ink-500">SIH26165</p>
            </div>
          </div>
        </div>

        <nav className="relative flex-1 space-y-5 overflow-y-auto px-3 py-5">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label}>
              <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-500">
                {section.label}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <NavItem key={item.to} {...item} />
                ))}
              </div>
            </div>
          ))}

          <div>
            <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-500">System</p>
            <div className="space-y-0.5">
              {hasRole("ADMIN") && <NavItem to="/audit" label="Audit Trail" icon={IconLock} />}
              {hasRole("ADMIN") && <NavItem to="/routing" label="Hi-Po Routing" icon={IconCheckShield} />}
              <NavItem to="/about" label="About / LSR Reference" icon={IconInfo} />
            </div>
          </div>
        </nav>

        <div className="relative border-t border-white/[0.08] px-4 py-4">
          <div className="mb-3 flex items-center gap-2.5">
            <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white/10 text-[12px] font-bold">
              {(user?.full_name || "?").slice(0, 1)}
            </span>
            <div className="min-w-0">
              <p className="truncate text-[12.5px] font-bold text-white">{user?.full_name}</p>
              <p className="truncate text-[10.5px] font-medium uppercase tracking-wide text-ink-500">
                {user?.role?.replace(/_/g, " ")}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-white/10 py-1.5 text-[12.5px] font-semibold text-ink-500 transition hover:border-white/20 hover:bg-white/5 hover:text-white"
          >
            <IconLogout className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-line bg-surface-raised/80 px-6 backdrop-blur">
          <p className="text-[13px] font-semibold text-ink_text-muted">
            <span className="text-ink_text-secondary">SIFGuard-OIL</span>
            <span className="mx-1.5 text-line">/</span>
            <span className="text-ink_text-primary">{currentLabel}</span>
          </p>
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full border border-line bg-white px-2.5 py-1 text-[11px] font-semibold text-ink_text-secondary sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-risk-nonsif" />
              Live demo data
            </span>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">
          <div className="w-full px-6 py-7 xl:px-8 2xl:px-10">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
