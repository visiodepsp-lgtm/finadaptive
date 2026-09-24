export default async function handler(req, res) {
  try {
    const response = await fetch('https://ohtvecqryqtlkejsgpam.supabase.co/auth/v1/settings');
    const data = await response.json();
    res.status(response.status).json({
      google_enabled: Boolean(data?.external?.google),
      status: response.status
    });
  } catch (error) {
    res.status(500).json({ google_enabled: false, status: 500 });
  }
}
