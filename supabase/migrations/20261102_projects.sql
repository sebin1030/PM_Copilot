-- Run in Supabase SQL Editor before enabling SUPABASE_URL in the backend.
create table if not exists public.projects (
  project_id text primary key check (project_id ~ '^[a-zA-Z0-9가-힣_-]+$'),
  owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists projects_owner_id_idx on public.projects (owner_id);
create index if not exists projects_updated_at_idx on public.projects (updated_at desc);

alter table public.projects enable row level security;
revoke all on public.projects from anon;
grant select, insert, update, delete on public.projects to authenticated;

drop policy if exists "Owners can select projects" on public.projects;
create policy "Owners can select projects" on public.projects for select to authenticated
  using ((select auth.uid()) is not null and owner_id = (select auth.uid()));

drop policy if exists "Owners can insert projects" on public.projects;
create policy "Owners can insert projects" on public.projects for insert to authenticated
  with check ((select auth.uid()) is not null and owner_id = (select auth.uid()));

drop policy if exists "Owners can update projects" on public.projects for update;
create policy "Owners can update projects" on public.projects for update to authenticated
  using ((select auth.uid()) is not null and owner_id = (select auth.uid()))
  with check ((select auth.uid()) is not null and owner_id = (select auth.uid()));

drop policy if exists "Owners can delete projects" on public.projects;
create policy "Owners can delete projects" on public.projects for delete to authenticated
  using ((select auth.uid()) is not null and owner_id = (select auth.uid()));

-- Keep DB ordering accurate without trusting a browser-provided timestamp.
create or replace function public.set_projects_updated_at()
returns trigger language plpgsql set search_path = public as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists projects_updated_at on public.projects;
create trigger projects_updated_at before update on public.projects
for each row execute function public.set_projects_updated_at();
