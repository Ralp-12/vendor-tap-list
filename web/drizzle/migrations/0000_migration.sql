CREATE TABLE public.vendor_checkins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL CHECK (char_length(full_name) BETWEEN 1 AND 120),
  company text NOT NULL CHECK (char_length(company) BETWEEN 1 AND 160),
  contact text NOT NULL CHECK (char_length(contact) BETWEEN 3 AND 200),
  on_display text NOT NULL CHECK (char_length(on_display) BETWEEN 1 AND 240),
  expertise text NOT NULL CHECK (expertise IN ('HVAC','Electrical','Plumbing','Fire & Life Safety','Building Automation & Controls','Elevators & Lifts','Power & Generators','Water Treatment','Equipment & Tools','Software & IoT','Roofing & Building Envelope','Janitorial & Grounds','Security Systems','Other')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX vendor_checkins_dedupe ON public.vendor_checkins (lower(btrim(full_name)), lower(btrim(company)), lower(btrim(contact)));
GRANT SELECT, INSERT ON public.vendor_checkins TO anon, authenticated;
GRANT ALL ON public.vendor_checkins TO service_role;
ALTER TABLE public.vendor_checkins ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anyone can check in" ON public.vendor_checkins FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anyone can view list" ON public.vendor_checkins FOR SELECT TO anon, authenticated USING (true);