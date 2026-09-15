# HockeyNet / FFHG arbitrage — data integration guide

Reverse-engineered API reference for pulling referee (arbitre) data out of the FFHG
"HockeyNet" platform. Written so another agent or developer can integrate directly.
All endpoints below were observed live and verified on **2026-07-28**.

---

## 1. Platform overview

Two AngularJS single-page apps over a **Laravel** JSON backend.

| App                               | Host                     | Who                    | Purpose                                                      |
| --------------------------------- | ------------------------ | ---------------------- | ------------------------------------------------------------ |
| Désignation des arbitres (admin)  | `hockeynet.fr`           | admin/designator       | assign officials to matches; admin scope over arbitrage data |
| Person fiche (admin)              | `hockeynet.fr`           | admin                  | per-person record (`/personnes/fiche/{id}/…`)                |
| Arbitrages (referee self-service) | `licencies.hockeynet.fr` | the referee themselves | own indisponibilités / distances / designations              |

Two distinct authorization scopes matter:

- **Designation-admin scope** (host `hockeynet.fr`): grants cross-arbitre read on the
  `/arbitrage/{personId}/*` endpoints. This is the scope that makes bulk export possible.
- **Person-level scope** (`/personnes/fiche/{personId}/…`): you can fully read **your own**
  person; for others you get only the `/apercu` overview. Everything else under a foreign
  person's fiche **302-redirects**.

`personId` throughout is the FFHG "personne" id (e.g. `64881`). It is **not** the licence
number; it is the internal id used in URLs and in `rencontre_officiels[].personne.id`.

---

## 2. Authentication & required headers

The backend is cookie-session based. The browser session cookie (HttpOnly) is set at login
and sent automatically with `credentials: 'include'`. **You cannot script the login** — a human
must be logged in in the browser; drive requests from that authenticated context (same-origin
`fetch`).

Every XHR must also send these two headers or the server replies `401 {"error":"Unauthorised"}`:

```
X-Requested-With: XMLHttpRequest
X-XSRF-TOKEN: <URL-decoded value of the XSRF-TOKEN cookie>
Accept: application/json, text/plain, */*
```

The `XSRF-TOKEN` cookie **rotates** — read it fresh before every call:

```js
const xsrf = () =>
  decodeURIComponent(
    (document.cookie.match(/XSRF-TOKEN=([^;]+)/) || [])[1] || "",
  );
const H = () => ({
  Accept: "application/json, text/plain, */*",
  "X-Requested-With": "XMLHttpRequest",
  "X-XSRF-TOKEN": xsrf(),
});
```

Notes / gotchas:

- Sessions are short-lived. A `401` on a call that worked earlier = session expired; the user
  must re-log-in in the browser, then retry.
- Cross-origin does not carry the session. To hit `hockeynet.fr` endpoints, run from a
  `hockeynet.fr` tab; for `licencies.hockeynet.fr`, run from that host's tab.
- The `POST /arbitrage/designation/export` (XLSX export) is triggered by a hidden `<form>`
  submit, not an XHR — so it will not appear in fetch/XHR hooks, and its body is form-encoded.

---

## 3. Endpoint reference

### 3.1 Arbitre roster / designations — `POST /arbitrage/designation/query`

Paginated list of match designations. Body = filter object; `{}` = defaults (current season).
Pagination via `?page=N` query param; `meta.last_page` gives page count.

Response: `{ data: [...], links, meta }`. Each `data[]` record:

```
{ id, rencontre_libelle, valide, date, heure,
  phase{...}, competition{...}, lieu_pratique{ id, code, nom, ... },
  etat{...},
  rencontre_officiels: [ { id, officiel_id, personne: { id, nom_complet, code_adherent,
                                                          licencesTypes, formations,
                                                          arbitrage_distances, ... } } ] }
```

Role labels are available in the same payload under `phase.competition_maitre.competition_officiels[]`.
Each entry carries `{ officiel_id, libelle, model_officiel{...} }`, and `rencontre_officiels[].officiel_id`
matches that `officiel_id`. Use `competition_officiels[].libelle` to label the row instead of hardcoding.

**This is the primary source of arbitre `personId`s** — dedupe `rencontre_officiels[].personne.id`
across all pages. Also the best source of person _identity_ data (name, licence types, formations)
without touching the gated fiche.

⚠️ Caveat: only surfaces arbitres who have been **designated**. A dedicated full-roster endpoint was
not found; the admin UI "Arbitre" filter appears to preload a roster client-side — to get the true
full roster, open that filter with the Network tab recording and capture the populating request.

### 3.2 Indisponibilités — `GET /arbitrage/{personId}/indisponibilites/init` ✅ cross-arbitre

Dates a referee is unavailable.

```
{ motifs: [ { id, libelle } ],                 // reason lookup
  routes: { add_indisponibilite, update_indisponibilite, delete_indisponibilite },
  indisponibilites: [ { id, motif_id, dates: { startDate:"dd/mm/yyyy", endDate:"dd/mm/yyyy" } } ],
  jourMaxSaisie }
```

Motif map: `2 Travail · 3 blessure · 4 vacances · 5 stage · 6 mondial · 7 Autre`.

Access: on `hockeynet.fr` (admin) returns 200 for **any** personId. On `licencies.hockeynet.fr`
it is owner-scoped (403 for others, 404 for non-existent).

Mutations (per arbitre): `POST …/indisponibilites/ajout`, `POST …/{indispo_id}/update`,
`DELETE …/{indispo_id}/delete`.

### 3.3 Distances — `GET /arbitrage/{personId}/distances/init` ✅ cross-arbitre

Travel distance + tolls from the arbitre to each rink.

```
{ structures: [ { id, nom, nom_court, code, ...,
                  lieux_de_pratique: [ { id, nom, libelle, structure, adresse,
                                         latitude, longitude, ... } ] } ],
  coordonnesPersonne: [...],
  personneDistances: [ { id, personne_id, lieu_pratique_id, distance /*km*/,
                         peages /*€ toll*/, valide, saison, created_at, updated_at } ],
  routes: { store_distances, calculer },
  permissions: { update_distance },
  avecCalculAuto }
```

Join `personneDistances[].lieu_pratique_id` → venue name via
`structures[].lieux_de_pratique[]` (build one global map; same for all arbitres).
~90% of ids resolve; unresolved = inactive/deleted venues, fall back to raw id.

### 3.4 Restrictions — `GET /arbitrage/{personId}/restrictions/init` ✅ cross-arbitre

Rinks the arbitre is restricted/barred from (typically own club / conflict of interest).

```
{ lieuxPratiques: [ { id, code, nom, structure, adresse, latitude, longitude, ... } ],  // lookup
  restrictionsPersonne: [ { id, personne_id, lieu_pratique_id, created_at, updated_at } ],
  routes }
```

Most arbitres have `restrictionsPersonne: []`. Resolve `lieu_pratique_id` via `lieuxPratiques[]`.

### 3.5 Calendrier — `GET /arbitrage/{personId}/calendrier/init` ✅ cross-arbitre

Rolling 12-month schedule view.

```
{ data_calendrier: [ { current, numero /*month 1-12*/, annee, libelle /*month name*/,
                       premier_jour /*ISO*/, dernier_jour /*ISO*/, jours: [ /* per-day entries */ ] } ],
  est_ouvert /*bool*/, saisons: [...], date_ouverture,
  routes: { store, update, export_ics, send_ics } }
```

`jours[]` carries per-day designations/availability; empty off-season. `export_ics` / `send_ics`
let you export the calendar as `.ics` or email it.

### 3.6 Designations (per arbitre) — `GET /arbitrage/{personId}/designations/init` ✅ cross-arbitre

Listed in the fiche route map; the per-arbitre view of their own assignments (contents known to
the client; not deeply profiled here). Same access model as the other `/arbitrage/{id}/*` routes.

### 3.7 Disponibilités ("rink per weekday") — self-only ❌ NOT cross-arbitre

Which weekdays the arbitre is available at each rink. Lives **only** under the person-gated fiche
path (no `/arbitrage/{id}/disponibilites/init` exists — that returns 404).

- Role list: `GET /personnes/fiche/{personId}/arbitrage/init` → `rolesPersonne[]`
  = `{ id, competitionId, phaseId, roleId, saison }`. The **`id`** is the `role_id` used below.
- Data: `GET /personnes/fiche/{personId}/roles/{role_id}/disponibilites/init`
  ```
  { structures: [...],
    disponibilites: [ { id, arbitrage_personne_id /*=role_id*/, structure_id /*club/rink*/,
                        disponibilites: { lun, mar, mer, jeu, ven, sam, dim } /*booleans*/,
                        created_at, updated_at } ] }
  ```
  Resolve `structure_id` → club name via the `structures[].{nom_court,nom}` from the distances
  endpoint (§3.3) or the same-response `structures`.
- Update: `POST /personnes/fiche/{personId}/roles/{role_id}/disponibilites/update`.

Access (verified): your own fiche works (bogus role_id → 404, i.e. route resolves). Any **other**
personId → **302 redirect**. Getting this for all referees requires either a higher
`personnes`/arbitrage-referent permission on the account, or a new backend endpoint under the
designation-admin scope.

### 3.8 Person fiche (identity/overview) — server-rendered, mostly gated

`/personnes/fiche/{id}/{apercu|infos|arbitrage|...}` are **server-rendered HTML pages** (data
embedded in the HTML; no clean JSON "person details" API). For another person you can load only
`/apercu`; the `/arbitrage` tab 302-redirects. For bulk identity data, use §3.1 instead.

Fiche-arbitrage route map (from `/personnes/fiche/{id}/arbitrage/init` → `routes`):
`add/update/delete_personne_role`, `load_data_for_disponibilite` (§3.7), `update_disponibilite`,
`init_indisponibilite`=§3.2, `init_distance`=§3.3, `init_designations`=§3.6,
`init_restrictions`=§3.4, `init_calendrier`=§3.5.

---

## 4. Access matrix

| Dataset                           | Endpoint                                                        | Cross-arbitre on admin (`hockeynet.fr`)? |
| --------------------------------- | --------------------------------------------------------------- | ---------------------------------------- |
| Designations list / roster        | `POST /arbitrage/designation/query`                             | ✅                                       |
| Designations XLSX export          | `POST /arbitrage/designation/export` (hidden-form)              | ✅                                       |
| Indisponibilités                  | `GET /arbitrage/{id}/indisponibilites/init`                     | ✅                                       |
| Distances                         | `GET /arbitrage/{id}/distances/init`                            | ✅                                       |
| Restrictions                      | `GET /arbitrage/{id}/restrictions/init`                         | ✅                                       |
| Calendrier                        | `GET /arbitrage/{id}/calendrier/init`                           | ✅                                       |
| Designations (per arbitre)        | `GET /arbitrage/{id}/designations/init`                         | ✅                                       |
| **Disponibilités (rink/weekday)** | `GET /personnes/fiche/{id}/roles/{role_id}/disponibilites/init` | ❌ self-only (302 for others)            |
| Fiche apercu (overview)           | `GET /personnes/fiche/{id}/apercu` (HTML)                       | ✅ overview only                         |
| Fiche arbitrage tab               | `GET /personnes/fiche/{id}/arbitrage`                           | ❌ self-only (302 → apercu)              |

---

## 5. Integration recipe (bulk pull)

```
1. Ensure a human is logged in to hockeynet.fr in the browser. Run all calls from a
   hockeynet.fr tab (same-origin), reading XSRF-TOKEN fresh each call (see §2).

2. Build the arbitre id set:
   - POST /arbitrage/designation/query?page=1..meta.last_page  (body {})
   - collect distinct rencontre_officiels[].personne.id (+ nom_complet)
   - (optional, for full roster) capture the admin "Arbitre" filter's populating request.

3. For each personId, GET the datasets you need:
   - indisponibilites/init  -> .indisponibilites  (map motif_id via .motifs)
   - distances/init         -> .personneDistances  (join lieu_pratique_id via structures[].lieux_de_pratique)
   - restrictions/init      -> .restrictionsPersonne (join lieu_pratique_id via lieuxPratiques)
   - calendrier/init        -> .data_calendrier[].jours

4. Disponibilités (self only): GET /personnes/fiche/{me}/arbitrage/init -> rolesPersonne[].id,
   then for each role GET /personnes/fiche/{me}/roles/{role_id}/disponibilites/init.

5. Throttle politely; handle 401 (session expired) by pausing for re-login. Cache the
   global structures/venue map once — it is identical across arbitres.
```

Minimal fetch helpers:

```js
const xsrf = () =>
  decodeURIComponent(
    (document.cookie.match(/XSRF-TOKEN=([^;]+)/) || [])[1] || "",
  );
const H = () => ({
  Accept: "application/json, text/plain, */*",
  "X-Requested-With": "XMLHttpRequest",
  "X-XSRF-TOKEN": xsrf(),
});
const getJSON = (u) =>
  fetch(u, { credentials: "include", headers: H() }).then((r) => r.json());
const postJSON = (u, b) =>
  fetch(u, {
    method: "POST",
    credentials: "include",
    headers: { ...H(), "Content-Type": "application/json;charset=UTF-8" },
    body: JSON.stringify(b || {}),
  }).then((r) => r.json());
```

---

## 6. Field dictionaries

**Indisponibilité motifs:** 2=Travail, 3=blessure, 4=vacances, 5=stage, 6=mondial, 7=Autre.

**Weekday keys (disponibilités):** lun, mar, mer, jeu, ven, sam, dim (booleans).

**Dates:** indisponibilités use `dd/mm/yyyy`; calendrier uses ISO 8601. Distances `distance` = km,
`peages` = € tolls. `saison` is the season's ending year (e.g. 2027 = 2026–2027 season).

---

## 7. Verified sample scale (2026-07-28, current designated set = 73 arbitres)

- Indisponibilités: 65/73 arbitres populated, 692 rows total.
- Distances: 70/73 populated, 9,232 rows total.
- Restrictions: mostly empty (e.g. person 12560 → 1).
- Calendrier: `jours[]` empty (off-season window).
- Disponibilités (own account, person 64881): 259 rows across 12 role/season records.

## 8. Ethics / scope note

This documents an authenticated user's own admin capabilities for legitimate federation
administration. The disponibilités person-level gate is a real authorization boundary and
should not be circumvented; obtain the proper permission or a backend endpoint instead.

---

## 9. Season roles per officiel (role + division) — verified 2026-09-15

A person's **season roles** (e.g. "Arbitre principal — Division 1", "Juge de ligne — Synerglace Ligue
Magnus") live in `rolesPersonne[]` returned by:

```
GET https://licencies.hockeynet.fr/personnes/fiche/{personId}/arbitrage/init
```

Response shape:

```
{ routes, saisons, personne,
  roles:          [ { id, libelle, saison, licence_types_requis, ... } ],   // roleId -> libelle
  competitions:   [ { id, libelle, saison, officiels[...] } ],             // competitionId -> libelle (division)
  phases:         [ { id, libelle, competition_id } ],
  rolesPersonne:  [ { id, competitionId, phaseId, roleId, saison } ] }      // THE season roles
```

Decode:

```
role_label     = roles[].libelle         where roles[].id == rolesPersonne[].roleId
competition    = competitions[].libelle  where competitions[].id == rolesPersonne[].competitionId
# => f"{role_label} - {competition}" e.g. "Arbitre principal - Division 1"
```

⚠️ Access: **self-only**. Own fiche → 200; any other personId → 403 on `licencies.hockeynet.fr`,
302→`/apercu` on `hockeynet.fr`. The FFHG **hid the roles tab from the licencié UI** (the
`/arbitrages` page now ships `config.roles = false`, so the tab is not rendered), but the endpoint
still returns the data.

Workaround for other arbitres with this account's permissions (designation-read only):

- `POST /arbitrage/designation/query` (any `saison`, `show_all: true`) → per-match
  `rencontre_officiels[].officiel_id` joined with
  `phase.competition_maitre.competition_officiels[].{officiel_id, libelle}` gives **role + competition
  per designation**. Distinct pairs per person ≈ their season roles (missing only roles held without
  any designation).
- `arbitres-assignable` (per rencontre, `officiel_id` filter) returns the eligible roster for a role,
  but needs `designation` write permission (403 otherwise).
- `/api/v1/login` (E-licence bearer-token API) rejects web credentials — not usable with these creds.
