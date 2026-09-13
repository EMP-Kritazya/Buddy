import { Link, useNavigate } from "@tanstack/react-router";
import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { dashboardNavLinks } from "@/components/dashboard/navLinks";
import { useDashboardUser } from "@/components/dashboard/DashboardContext";
import { Button } from "@/components/ui/button";
import type { User } from "@/types";

type ProfileField = "name" | "university" | "major" | "peakTime" | "goal";

const profileFields: Array<{ key: ProfileField; label: string; multiline?: boolean }> = [
  { key: "name", label: "Name" },
  { key: "university", label: "University" },
  { key: "major", label: "Major" },
  { key: "peakTime", label: "Peak focus time" },
  { key: "goal", label: "Main goal", multiline: true },
];

function ProfileModal({ user, onClose, onSave }: { user: User; onClose: () => void; onSave: (user: User) => void }) {
  const [draft, setDraft] = useState(user);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSave(draft);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-ink/30 px-5" role="presentation" onMouseDown={onClose}>
      <div className="w-full max-w-[480px] rounded-[4px] border border-border bg-surface p-8" role="dialog" aria-modal="true" aria-labelledby="profile-title" onMouseDown={(event) => event.stopPropagation()}>
        <h2 id="profile-title" className="mb-7 font-serif text-[28px] font-normal">Edit profile</h2>
        <form onSubmit={submit}>
          <div className="space-y-5">
            {profileFields.map((field) => (
              <label key={field.key} className="block text-[12px] text-ink-3">
                {field.label}
                {field.multiline ? (
                  <textarea value={draft[field.key]} onChange={(event) => setDraft((current) => ({ ...current, [field.key]: event.target.value }))} rows={3} className="mt-1 block w-full resize-none border-0 border-b border-border bg-transparent px-0 py-2 text-[14px] text-ink outline-none focus:border-accent" />
                ) : (
                  <input value={draft[field.key]} onChange={(event) => setDraft((current) => ({ ...current, [field.key]: event.target.value }))} className="mt-1 block w-full border-0 border-b border-border bg-transparent px-0 py-2 text-[14px] text-ink outline-none focus:border-accent" />
                )}
              </label>
            ))}
          </div>
          <div className="mt-8 flex gap-3">
            <Button type="submit" className="h-auto rounded-[3px] bg-accent px-5 py-[10px] text-[13px] text-surface shadow-none hover:bg-accent hover:brightness-90">Save changes</Button>
            <Button type="button" variant="outline" onClick={onClose} className="h-auto rounded-[3px] border-border bg-transparent px-5 py-[10px] text-[13px] text-ink shadow-none hover:bg-canvas">Cancel</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function TopNavigation() {
  const navigate = useNavigate();
  const { user, saveUser } = useDashboardUser();
  const [profileOpen, setProfileOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!profileRef.current?.contains(event.target as Node)) setProfileOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const signOut = () => {
    window.localStorage.clear();
    void navigate({ to: "/" });
  };

  return (
    <>
      <header className="sticky top-0 z-50 h-14 border-b border-border bg-canvas px-5 sm:px-8 lg:px-10">
        <div className="relative flex h-full items-center justify-between">
          <Link to="/dashboard" className="font-serif text-[20px] text-ink">Buddy</Link>

          <nav className="absolute inset-y-0 left-1/2 hidden -translate-x-1/2 items-center lg:flex" aria-label="Main navigation">
            {dashboardNavLinks.map((link) => (
              <Link key={link.to} to={link.to} activeOptions={{ exact: true }} className="flex h-14 items-center border-b-2 border-transparent px-4 text-[14px] text-ink-2 transition-all duration-150 hover:text-ink" activeProps={{ className: "border-accent text-ink" }}>{link.label}</Link>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <Button type="button" variant="ghost" size="icon" aria-label={menuOpen ? "Close navigation" : "Open navigation"} onClick={() => setMenuOpen((open) => !open)} className="hidden size-8 rounded-[3px] text-ink shadow-none hover:bg-border-2 md:inline-flex lg:hidden">{menuOpen ? <X /> : <Menu />}</Button>
            <div ref={profileRef} className="relative">
              <Button type="button" aria-label="Open profile menu" aria-expanded={profileOpen} onClick={() => setProfileOpen((open) => !open)} className="size-8 rounded-full bg-accent p-0 text-[13px] font-medium text-surface shadow-none hover:bg-accent hover:brightness-90">{user.name.charAt(0).toUpperCase()}</Button>
              {profileOpen ? (
                <div className="absolute right-0 top-10 z-[100] min-w-[200px] rounded-[4px] border border-border bg-surface py-2">
                  <div className="px-4 pb-2 pt-3"><p className="text-[14px] font-medium">{user.name} {user.lastName}</p><p className="text-[12px] text-ink-3">{user.email}</p></div>
                  <div className="border-t border-border-2 py-1">
                    <Button type="button" variant="ghost" onClick={() => { setProfileOpen(false); setEditOpen(true); }} className="h-auto w-full justify-start rounded-none px-4 py-[10px] text-[13px] font-normal text-ink shadow-none hover:bg-canvas">Edit profile</Button>
                    <Button asChild variant="ghost" className="h-auto w-full justify-start rounded-none px-4 py-[10px] text-[13px] font-normal text-ink shadow-none hover:bg-canvas"><Link to="/settings">Settings</Link></Button>
                  </div>
                  <div className="border-t border-border-2 pt-1"><Button type="button" variant="ghost" onClick={signOut} className="h-auto w-full justify-start rounded-none px-4 py-[10px] text-[13px] font-normal text-incident shadow-none hover:bg-signout-hover hover:text-incident">Sign out</Button></div>
                </div>
              ) : null}
            </div>
          </div>

          {menuOpen ? (
            <nav className="absolute right-0 top-14 hidden min-w-[200px] rounded-[4px] border border-border bg-surface py-2 md:block lg:hidden" aria-label="Tablet navigation">
              {dashboardNavLinks.map((link) => <Link key={link.to} to={link.to} onClick={() => setMenuOpen(false)} className="block px-4 py-3 text-[14px] text-ink-2 hover:bg-canvas hover:text-ink" activeProps={{ className: "text-ink font-medium" }}>{link.label}</Link>)}
            </nav>
          ) : null}
        </div>
      </header>
      {editOpen ? <ProfileModal user={user} onClose={() => setEditOpen(false)} onSave={saveUser} /> : null}
    </>
  );
}