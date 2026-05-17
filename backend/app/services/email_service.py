import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def send_plate_alert(
    to: str,
    plate: str,
    camera_name: str,
    location: str = "",
    detected_at: str = "",
    image_url: str = "",
) -> bool:
    if not settings.RESEND_API_KEY:
        return False

    import resend
    resend.api_key = settings.RESEND_API_KEY

    image_html = (
        f'<img src="{image_url}" style="max-width:600px;border-radius:4px;margin-top:12px;" />'
        if image_url
        else ""
    )

    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;">
      <h2 style="color:#c0392b;margin-top:0;">&#9888;&#65039; Alerta de Placa Detectada</h2>
      <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
        <tr style="background:#f8f8f8;">
          <td style="padding:10px 12px;font-weight:bold;width:30%;">Placa</td>
          <td style="padding:10px 12px;font-size:20px;font-weight:bold;">{plate}</td>
        </tr>
        <tr>
          <td style="padding:10px 12px;font-weight:bold;">C&#226;mera</td>
          <td style="padding:10px 12px;">{camera_name}</td>
        </tr>
        <tr style="background:#f8f8f8;">
          <td style="padding:10px 12px;font-weight:bold;">Local</td>
          <td style="padding:10px 12px;">{location or "—"}</td>
        </tr>
        <tr>
          <td style="padding:10px 12px;font-weight:bold;">Data/Hora</td>
          <td style="padding:10px 12px;">{detected_at}</td>
        </tr>
      </table>
      {image_html}
      <p style="margin-top:24px;">
        <a href="http://localhost:3000" style="background:#2563eb;color:#fff;padding:10px 20px;
           text-decoration:none;border-radius:4px;">Acessar o Sistema</a>
      </p>
    </div>
    """

    try:
        resend.Emails.send(
            {
                "from": settings.RESEND_FROM_EMAIL,
                "to": [to],
                "subject": f"⚠️ Placa {plate} detectada — {camera_name}",
                "html": html,
            }
        )
        return True
    except Exception:
        logger.warning("Failed to send alert email to %s", to, exc_info=True)
        return False


# Backwards-compat alias used by older code
send_alert_email = send_plate_alert
