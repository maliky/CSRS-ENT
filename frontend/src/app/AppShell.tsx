import {
  BriefcaseBusiness,
  CalendarDays,
  ChevronDown,
  ClipboardList,
  FileCheck2,
  FolderKanban,
  Gauge,
  Lightbulb,
  ListPlus,
  LogOut,
  Menu,
  Network,
  Building2,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Users,
  UserRoundCheck,
  UserRoundCog,
  ListX,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "../lib/router";
import { apiFetch } from "../lib/api/client";
import type { Session } from "../lib/api/types";
import { ErrorState, Skeleton } from "../components/ui";
import { useApi } from "../lib/useApi";
import styles from "./shell.module.css";
import { PasswordChangePage } from "../features/users/PasswordChangePage";

const SIDEBAR_STORAGE_KEY = "csrs_ent.sidebar.collapsed";

export function AppShell() {
  const {
    data: session,
    error,
    loading,
    reload,
    setData,
  } = useApi<Session>("/api/v1/session/");
  const [collapsed, setCollapsed] = useState(
    () => window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true",
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [switchingRole, setSwitchingRole] = useState(false);
  const [roleError, setRoleError] = useState("");
  const mobileToggle = useRef<HTMLButtonElement>(null);
  const mobileClose = useRef<HTMLButtonElement>(null);
  const location = useLocation();

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    function closeOnEscape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape" && mobileOpen) {
        setMobileOpen(false);
        mobileToggle.current?.focus();
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [mobileOpen]);

  if (loading)
    return (
      <main className={styles.loadingMain}>
        <Skeleton label="Chargement de la session" />
      </main>
    );
  if (error || !session)
    return (
      <main className={styles.loadingMain}>
        <ErrorState
          error={error ?? new Error("Session indisponible")}
          retry={reload}
        />
      </main>
    );

  async function signOut() {
    await apiFetch<void>("/api/v1/session/logout/", { method: "POST" });
    window.location.assign("/app/");
  }

  async function switchRole(roleCode: string | null) {
    setSwitchingRole(true);
    setRoleError("");
    try {
      setData(
        await apiFetch<Session>("/api/v1/session/role/", {
          method: "POST",
          body: JSON.stringify({ role_code: roleCode }),
        }),
      );
    } catch (caught) {
      setRoleError(
        caught instanceof Error
          ? caught.message
          : "Le rôle n'a pas pu être activé.",
      );
    } finally {
      setSwitchingRole(false);
    }
  }

  if (session.capabilities.password_change_required)
    return <PasswordChangePage onComplete={reload} onLogout={signOut} />;

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
      return next;
    });
  }

  function openMobile() {
    setMobileOpen(true);
    window.requestAnimationFrame(() => mobileClose.current?.focus());
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? `${styles.navItem} ${styles.active}` : styles.navItem;
  const iconSize = 20;

  return (
    <div
      className={`${styles.shell} ${collapsed ? styles.shellCollapsed : ""}`}
    >
      <a className="skip-link" href="#contenu">
        Aller au contenu
      </a>
      <header className={styles.mobileBar}>
        <NavLink to="/" className={styles.mobileBrand}>
          CSRS ENT
        </NavLink>
        <button
          ref={mobileToggle}
          type="button"
          className={styles.iconButton}
          aria-label="Ouvrir le menu"
          aria-controls="navigation-principale"
          aria-expanded={mobileOpen}
          onClick={openMobile}
        >
          <Menu aria-hidden="true" />
        </button>
      </header>
      {mobileOpen && (
        <button
          className={styles.backdrop}
          type="button"
          aria-label="Fermer le menu"
          onClick={() => {
            setMobileOpen(false);
            mobileToggle.current?.focus();
          }}
        />
      )}
      <aside
        id="navigation-principale"
        className={`${styles.sidebar} ${collapsed ? styles.collapsed : ""} ${mobileOpen ? styles.mobileOpen : ""}`}
        aria-label="Navigation principale"
      >
        <div className={styles.sidebarHeader}>
          <NavLink to="/" className={styles.brand} title="CSRS ENT">
            <span className={styles.brandMark}>CS</span>
            <span className={styles.brandLabel}>CSRS ENT</span>
          </NavLink>
          <button
            ref={mobileClose}
            type="button"
            className={`${styles.iconButton} ${styles.mobileClose}`}
            aria-label="Fermer le menu"
            onClick={() => {
              setMobileOpen(false);
              mobileToggle.current?.focus();
            }}
          >
            <X aria-hidden="true" />
          </button>
        </div>
        <nav className={styles.nav}>
          <details className={styles.navGroup} open>
            <summary className={styles.navGroupSummary} title="Travail">
              <BriefcaseBusiness size={iconSize} aria-hidden="true" />
              <span className={styles.navLabel}>Travail</span>
              <ChevronDown
                className={styles.groupChevron}
                size={16}
                aria-hidden="true"
              />
            </summary>
            <div className={styles.navGroupItems}>
              <NavLink to="/" end className={navClass} title="Mes tâches">
                <ClipboardList size={iconSize} aria-hidden="true" />
                <span className={styles.navLabel}>Mes tâches</span>
              </NavLink>
              {session.capabilities.view_team && (
                <NavLink to="/equipe" className={navClass} title="Mon équipe">
                  <Users size={iconSize} aria-hidden="true" />
                  <span className={styles.navLabel}>Mon équipe</span>
                </NavLink>
              )}
              <NavLink
                to="/propositions"
                className={navClass}
                title="Propositions"
              >
                <Lightbulb size={iconSize} aria-hidden="true" />
                <span className={styles.navLabel}>Propositions</span>
              </NavLink>
              {session.capabilities.create_task && (
                <NavLink
                  to="/taches/nouvelle"
                  className={navClass}
                  title="Affecter"
                >
                  <ListPlus size={iconSize} aria-hidden="true" />
                  <span className={styles.navLabel}>Affecter</span>
                </NavLink>
              )}
              {session.capabilities.delete_tasks && (
                <NavLink
                  to="/administration/taches"
                  className={navClass}
                  title="Gestion des tâches"
                >
                  <ListX size={iconSize} aria-hidden="true" />
                  <span className={styles.navLabel}>Gérer les tâches</span>
                </NavLink>
              )}
            </div>
          </details>
          <details className={styles.navGroup} open>
            <summary className={styles.navGroupSummary} title="Pilotage">
              <Gauge size={iconSize} aria-hidden="true" />
              <span className={styles.navLabel}>Pilotage</span>
              <ChevronDown
                className={styles.groupChevron}
                size={16}
                aria-hidden="true"
              />
            </summary>
            <div className={styles.navGroupItems}>
              {session.capabilities.view_weekly_agenda && (
                <NavLink
                  to="/agenda"
                  className={navClass}
                  title="Agenda hebdomadaire"
                >
                  <CalendarDays size={iconSize} aria-hidden="true" />
                  <span className={styles.navLabel}>Agenda</span>
                </NavLink>
              )}
              {session.capabilities.manage_availability && (
                <NavLink
                  to="/absences"
                  className={navClass}
                  title="Absences et missions"
                >
                  <UserRoundCheck size={iconSize} aria-hidden="true" />
                  <span className={styles.navLabel}>Absences et missions</span>
                </NavLink>
              )}
              {session.capabilities.manage_research_projects && (
                <NavLink
                  to="/projets"
                  className={navClass}
                  title="Projets de recherche"
                >
                  <FolderKanban size={iconSize} aria-hidden="true" />
                  <span className={styles.navLabel}>Projets</span>
                </NavLink>
              )}
              {session.capabilities.manage_processes && (
                <NavLink
                  to="/procedures"
                  className={navClass}
                  title="Procédures métier"
                >
                  <FileCheck2 size={iconSize} aria-hidden="true" />
                  <span className={styles.navLabel}>Procédures</span>
                </NavLink>
              )}
            </div>
          </details>
          {(session.capabilities.manage_users ||
            session.capabilities.manage_organization ||
            session.capabilities.manage_partners) && (
            <details className={styles.navGroup} open>
              <summary
                className={styles.navGroupSummary}
                title="Administration"
              >
                <Settings size={iconSize} aria-hidden="true" />
                <span className={styles.navLabel}>Administration</span>
                <ChevronDown
                  className={styles.groupChevron}
                  size={16}
                  aria-hidden="true"
                />
              </summary>
              <div className={styles.navGroupItems}>
                {session.capabilities.manage_users && (
                  <NavLink
                    to="/administration/utilisateurs"
                    className={navClass}
                    title="Gestion des utilisateurs"
                  >
                    <UserRoundCog size={iconSize} aria-hidden="true" />
                    <span className={styles.navLabel}>Utilisateurs</span>
                  </NavLink>
                )}
                {session.capabilities.manage_organization && (
                  <NavLink
                    to="/administration/organigramme"
                    className={navClass}
                    title="Organigramme"
                  >
                    <Network size={iconSize} aria-hidden="true" />
                    <span className={styles.navLabel}>Organigramme</span>
                  </NavLink>
                )}
                {session.capabilities.manage_partners && (
                  <NavLink
                    to="/administration/organisations"
                    className={navClass}
                    title="Organisations partenaires"
                  >
                    <Building2 size={iconSize} aria-hidden="true" />
                    <span className={styles.navLabel}>Organisations</span>
                  </NavLink>
                )}
              </div>
            </details>
          )}
        </nav>
        <div className={styles.sidebarSecondary}>
          {session.role_switcher.can_switch && (
            <div className={styles.roleSwitcher}>
              <label htmlFor="effective-role">Voir comme</label>
              <select
                id="effective-role"
                aria-label="Rôle actif"
                value={session.role_switcher.active_code ?? ""}
                disabled={switchingRole}
                onChange={(event) =>
                  void switchRole(event.target.value || null)
                }
              >
                <option value="">Administrateur IT</option>
                {session.role_switcher.roles.map((role) => (
                  <option key={role.code} value={role.code}>
                    {role.label}
                  </option>
                ))}
              </select>
              {roleError && <small role="alert">{roleError}</small>}
            </div>
          )}
          <button
            type="button"
            className={styles.navItem}
            title="Déconnexion"
            onClick={() => void signOut()}
          >
            <LogOut size={iconSize} aria-hidden="true" />
            <span className={styles.navLabel}>Déconnexion</span>
          </button>
          <div className={styles.user} title={session.user.name}>
            <span className={styles.avatar} aria-hidden="true">
              {session.user.name.slice(0, 1).toUpperCase()}
            </span>
            <span className={styles.userDetails}>
              <strong>{session.user.name}</strong>
              <small>{session.user.position}</small>
            </span>
          </div>
        </div>
        <button
          type="button"
          className={`${styles.collapseButton} ${styles.desktopToggle}`}
          aria-label={collapsed ? "Déployer le menu" : "Réduire le menu"}
          aria-expanded={!collapsed}
          onClick={toggleCollapsed}
          title={collapsed ? "Déployer le menu" : "Réduire le menu"}
        >
          {collapsed ? (
            <PanelLeftOpen size={20} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={20} aria-hidden="true" />
          )}
          <span className={styles.navLabel}>
            {collapsed ? "Déployer" : "Réduire"}
          </span>
        </button>
      </aside>
      <div className={styles.content}>
        {session.role_switcher.active_label && (
          <div className={styles.roleBanner} role="status">
            <strong>Vue active : {session.role_switcher.active_label}.</strong>{" "}
            Vous restez identifié comme administrateur IT et vos actions sont
            auditées sous votre identité.
          </div>
        )}
        {!session.reporting.write_enabled && (
          <div className={styles.mirrorBanner} role="status">
            <strong>Consultation synchronisée.</strong> Les tâches, absences,
            visites et agendas sont encore saisis dans{" "}
            <a href={session.reporting.source_url}>CSRS Report</a> puis recopiés
            automatiquement dans CSRS ENT.
            {session.reporting.last_success_at && (
              <small>
                Dernière synchronisation réussie :{" "}
                {session.reporting.last_success_at.replace("T", " ")}.
              </small>
            )}
          </div>
        )}
        <main id="contenu" className={styles.main} tabIndex={-1}>
          <Outlet context={session} />
        </main>
        <footer className={styles.footer}>
          CSRS ENT · Suivi collaboratif et responsable
        </footer>
      </div>
    </div>
  );
}
