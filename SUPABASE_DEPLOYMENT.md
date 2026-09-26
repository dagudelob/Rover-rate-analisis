# Supabase Deployment & Setup Guide

This guide walks you through deploying and configuring the database schema, security policies, environment variables, and data migration for **Rover Market Intelligence** on [Supabase](https://supabase.com).

---

## Prerequisites

- A Supabase account ([supabase.com](https://supabase.com)).
- An active Supabase project created in your organization.
- Local repository setup with Python virtual environment configured (`.venv`).

---

## Step 1: Create a Supabase Project

1. Log in to [Supabase Dashboard](https://supabase.com/dashboard).
2. Click **New project**.
3. Fill in the project details:
   - **Name:** `rover-market-intelligence` (or your chosen name).
   - **Database Password:** Store this securely (needed for direct PostgreSQL connections or pooler).
   - **Region:** Select the region closest to your target scraping region or users.
4. Wait for database provisioning to finish.

---

## Step 2: Apply the Database Schema & RLS Policies

The repository includes a ready-to-run idempotent SQL script with tables, indexes, Row Level Security (RLS), and views: [supabase_schema.sql](file:///home/dagudelo/code/Projects/friday/rover/scripts/supabase_schema.sql).

### Option A: Using the Supabase Dashboard SQL Editor (Recommended)
1. In your project dashboard, navigate to **SQL Editor** on the left navigation bar.
2. Click **New query**.
3. Open and copy the entire contents of [scripts/supabase_schema.sql](file:///home/dagudelo/code/Projects/friday/rover/scripts/supabase_schema.sql).
4. Paste the SQL into the editor and click **Run**.
5. Verify that the query executes with `Success. No rows returned`.

### What gets created:
- **Tables:**
  - `public.search_sessions`: Scraping execution sessions and aggregate statistics.
  - `public.sitters`: Master sitter profiles with unique constraints on `member_id` and `profile_url`.
  - `public.session_sitters`: Join table linking sessions to sitters.
  - `public.sitter_services`: Sitter rates and service breakdown matrix.
- **Indexes:** Composite B-tree indexes for fast querying by service, location, and rating.
- **Views:**
  - `public.view_sitter_market_summary`: Aggregated profile with active services array.
  - `public.view_service_price_distributions`: Market percentiles and averages grouped by service type.
- **Security (RLS):**
  - Read-only (`SELECT`) access for `anon` and `authenticated` roles.
  - Full write (`ALL`) access restricted to `service_role`.

---

## Step 3: Retrieve Project API Credentials

1. In the Supabase Dashboard, click on **Project Settings** (gear icon at the bottom left).
2. Navigate to **API**.
3. Copy the following keys:
   - **Project URL:** e.g., `https://<project-ref>.supabase.co`
   - **anon / public key:** Used for read operations / client queries.
   - **service_role key (secret):** Used by backend ingestion, scrapers, and data migrations to bypass RLS. Keep this secret!

---

## Step 4: Configure Local Environment Variables

1. In your local repository root, create or update `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set your Supabase credentials:
   ```env
   # Database Configuration
   DB_PATH=rover_market.db

   # Supabase Integration
   SUPABASE_URL=https://<your-project-ref>.supabase.co
   SUPABASE_KEY=<your-anon-or-service-role-key>
   SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>

   # Server & CORS
   CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

   # Scraper Settings
   SCRAPER_MAX_PAGES=15
   SCRAPER_MAX_RESULTS=200
   ```

> [!TIP]
> For backend data ingestion scripts and migrations, ensure `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_KEY` set to the service role key) is provided so inserts are permitted by PostgreSQL RLS.

---

## Step 5: (Optional) Migrate Existing SQLite Data

If you have historical scraping data in `rover_market.db`, run the migration script:

1. Activate your virtual environment:
   ```bash
   source .venv/bin/activate
   ```
2. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Execute the migration script:
   ```bash
   python scripts/migrate_sqlite_to_supabase.py
   ```
4. Verify the output logs. The script handles upserts and ID remapping across `sitters`, `search_sessions`, `session_sitters`, and `sitter_services`.

---

## Step 6: Verify in Supabase Dashboard

1. Navigate to **Table Editor** in Supabase:
   - Check `sitters` to verify profiles and coordinates.
   - Check `search_sessions` for past scraping batches.
   - Check `sitter_services` for price breakdowns.
2. Go to **SQL Editor** and run a verification query:
   ```sql
   SELECT * FROM public.view_sitter_market_summary LIMIT 10;
   ```
   ```sql
   SELECT * FROM public.view_service_price_distributions;
   ```

---

## Step 7: Running the Application with Supabase

Start the FastAPI application:
```bash
uvicorn app.main:app --reload --port 8000
```
Open [http://localhost:8000](http://localhost:8000) or check API docs at [http://localhost:8000/docs](http://localhost:8000/docs).
The application will automatically utilize the configured Supabase client when `SUPABASE_URL` and `SUPABASE_KEY` are present.
