export async function runScoutAgent() {
  const niche = document.getElementById('nicheFilter')?.value.trim();
  const area = document.getElementById('areaFilter')?.value.trim();
  const statusDiv = document.getElementById('statusMessage');

  if (!niche || !area) {
    statusDiv.textContent = 'Sila pilih kedua-dua Niche dan Kawasan.';
    return;
  }

  statusDiv.textContent = 'Menjalankan Scout Agent (backend Python)...';

  try {
    const response = await fetch('http://localhost:8000/api/run-scout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ niche, area }),
    });

    const result = await response.json();

    if (!response.ok || result.status !== 'success') {
      statusDiv.textContent = 'Ralat Scout: ' + (result.message || 'Ralat tidak diketahui');
      return;
    }

    statusDiv.textContent = 'Scout Agent sedang berjalan di latar belakang. Sila tunggu 10-20 saat, kemudian tekan Refresh.';
    if (typeof window.fetchLeads === 'function') {
      window.fetchLeads();
    }
  } catch (err) {
    console.error('Ralat Scout:', err);
    statusDiv.textContent = 'Ralat Scout: ' + err.message;
  }
}
