import { Building2, Pencil, Plus, ArchiveRestore } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "../../components/ui";
import { apiFetch } from "../../lib/api/client";
import type {
  ManagedPartner,
  PartnerAdministration,
} from "../../lib/api/types";
import { useApi } from "../../lib/useApi";

type PartnerForm = {
  id: number | null;
  name: string;
  email: string;
  phone: string;
  active: boolean;
  state_token: string;
};

const EMPTY_PARTNER: PartnerForm = {
  id: null,
  name: "",
  email: "",
  phone: "",
  active: true,
  state_token: "",
};

function formFor(partner: ManagedPartner): PartnerForm {
  return {
    id: partner.id,
    name: partner.name,
    email: partner.email,
    phone: partner.phone,
    active: partner.active,
    state_token: partner.state_token,
  };
}

export function PartnerManagementPage() {
  const [state, setState] = useState<"active" | "inactive">("active");
  const partners = useApi<PartnerAdministration>(
    `/api/v1/partners/?state=${state}`,
  );
  const [form, setForm] = useState<PartnerForm>(EMPTY_PARTNER);
  const [message, setMessage] = useState("");
  const [mutationError, setMutationError] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setMutationError("");
    try {
      await apiFetch<ManagedPartner>(
        form.id ? `/api/v1/partners/${form.id}/` : "/api/v1/partners/",
        {
          method: form.id ? "PATCH" : "POST",
          body: JSON.stringify({
            name: form.name,
            email: form.email,
            phone: form.phone,
            active: form.active,
            ...(form.id ? { state_token: form.state_token } : {}),
          }),
        },
      );
      setMessage(form.id ? "Organisation mise à jour." : "Organisation créée.");
      setForm(EMPTY_PARTNER);
      await partners.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Enregistrement impossible.",
      );
    }
  }

  async function archive(partner: ManagedPartner) {
    setMessage("");
    setMutationError("");
    try {
      await apiFetch(`/api/v1/partners/${partner.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          name: partner.name,
          email: partner.email,
          phone: partner.phone,
          active: !partner.active,
          state_token: partner.state_token,
        }),
      });
      setMessage(
        partner.active ? "Organisation archivée." : "Organisation réactivée.",
      );
      await partners.reload();
    } catch (caught) {
      setMutationError(
        caught instanceof Error ? caught.message : "Mise à jour impossible.",
      );
    }
  }

  if (partners.loading)
    return <Skeleton label="Chargement des organisations" />;
  if (partners.error || !partners.data)
    return (
      <ErrorState
        error={partners.error ?? new Error("Organisations indisponibles")}
        retry={() => void partners.reload()}
      />
    );

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Administration IT</p>
          <h1>Organisations</h1>
          <p>
            Créez les bailleurs et partenaires Odoo qui pourront être
            sélectionnés dans les projets.
          </p>
        </div>
      </header>
      {message && (
        <p className="success-banner" role="status">
          {message}
        </p>
      )}
      {mutationError && (
        <p className="error-banner" role="alert">
          {mutationError}
        </p>
      )}
      <Card>
        <form className="stack" onSubmit={(event) => void save(event)}>
          <h2>
            {form.id ? "Modifier l’organisation" : "Nouvelle organisation"}
          </h2>
          <div className="form-grid">
            <div className="form-field wide">
              <label htmlFor="partner-name">Nom</label>
              <input
                id="partner-name"
                required
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="partner-email">Email</label>
              <input
                id="partner-email"
                type="email"
                value={form.email}
                onChange={(event) =>
                  setForm({ ...form, email: event.target.value })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="partner-phone">Téléphone</label>
              <input
                id="partner-phone"
                value={form.phone}
                onChange={(event) =>
                  setForm({ ...form, phone: event.target.value })
                }
              />
            </div>
          </div>
          <div className="cluster">
            <Button>
              <Plus size={18} aria-hidden="true" />{" "}
              {form.id ? "Enregistrer" : "Créer"}
            </Button>
            {form.id && (
              <Button
                type="button"
                variant="quiet"
                onClick={() => setForm(EMPTY_PARTNER)}
              >
                Annuler
              </Button>
            )}
          </div>
        </form>
      </Card>
      <div className="cluster">
        <Button
          variant={state === "active" ? "primary" : "secondary"}
          onClick={() => setState("active")}
        >
          Actives
        </Button>
        <Button
          variant={state === "inactive" ? "primary" : "secondary"}
          onClick={() => setState("inactive")}
        >
          Archivées
        </Button>
      </div>
      {!partners.data.items.length ? (
        <EmptyState title="Aucune organisation">
          Créez une organisation avant de l’associer à un projet.
        </EmptyState>
      ) : (
        <div className="grid">
          {partners.data.items.map((partner) => (
            <Card key={partner.id}>
              <Building2 aria-hidden="true" />
              <h2>{partner.name}</h2>
              {partner.email && <p>{partner.email}</p>}
              {partner.phone && <p>{partner.phone}</p>}
              <div className="cluster">
                <Button
                  variant="secondary"
                  onClick={() => setForm(formFor(partner))}
                >
                  <Pencil size={17} aria-hidden="true" /> Modifier
                </Button>
                <Button variant="quiet" onClick={() => void archive(partner)}>
                  <ArchiveRestore size={17} aria-hidden="true" />
                  {partner.active ? "Archiver" : "Réactiver"}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
