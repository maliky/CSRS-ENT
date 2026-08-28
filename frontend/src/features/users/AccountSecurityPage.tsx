import { ErrorState, Skeleton } from "../../components/ui";
import type { Session } from "../../lib/api/types";
import { useApi } from "../../lib/useApi";
import { PasswordChangePage } from "./PasswordChangePage";

export function AccountSecurityPage() {
  const { data, error, loading, reload } = useApi<Session>("/api/v1/session/");
  if (loading) return <Skeleton label="Chargement du compte" />;
  if (error || !data)
    return (
      <ErrorState
        error={error ?? new Error("Compte indisponible")}
        retry={reload}
      />
    );
  return (
    <PasswordChangePage
      forced={false}
      professionalEmail={data.professional_email}
      onComplete={() => window.location.assign("/connexion/")}
      onLogout={() => window.location.assign("/app/")}
    />
  );
}
