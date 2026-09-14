import { Link } from "react-router-dom";
import { Button } from "../components/ui";
import { IconAlertTriangle } from "../components/icons";

export default function NotFoundPage() {
  return (
    <div className="bg-grain flex min-h-screen flex-col items-center justify-center gap-4 bg-ink-950 text-center text-white">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/15 text-accent-400">
        <IconAlertTriangle className="h-7 w-7" />
      </span>
      <p className="text-6xl font-extrabold tracking-tight">404</p>
      <p className="text-white/50">This page doesn't exist — or was never analyzed.</p>
      <Button as={Link} to="/dashboard" variant="accent" size="lg">
        Back to Dashboard
      </Button>
    </div>
  );
}
