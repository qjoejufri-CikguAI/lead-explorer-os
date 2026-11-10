import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

const SUPABASE_URL = 'https://ypcccthqbnkurkslsvdi.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj';

export const supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
