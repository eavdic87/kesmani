"""
Real-time alert system for KešMani portfolio positions.

Checks open positions against live prices and returns alert dicts
for stop-loss breaches and price-target hits.  Optionally sends
email notifications via the existing email_config.

Public functions
---------------
check_stop_alerts(positions)   → positions where live_price ≤ stop_loss
check_target_alerts(positions) → positions at Target 1 or Target 2
send_alert_email(alerts)       → email notification (requires email_config)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert checkers
# ---------------------------------------------------------------------------

def check_stop_alerts(positions: list[dict]) -> list[dict]:
    """
    Return positions where the live price has hit or fallen below stop_loss.

    Parameters
    ----------
    positions:
        List of enriched position dicts (output of ``get_portfolio_summary``).
        Each dict must have: ticker, live_price, stop_loss.

    Returns
    -------
    Subset of positions that have triggered a stop alert.
    Each returned dict has an extra ``alert_type`` key set to ``"STOP"``.
    """
    alerts: list[dict] = []
    for pos in positions:
        live = pos.get("live_price")
        stop = pos.get("stop_loss")
        if live is not None and stop is not None and live <= stop:
            alerts.append({**pos, "alert_type": "STOP"})
    return alerts


def check_target_alerts(positions: list[dict]) -> list[dict]:
    """
    Return positions that have hit Target 1 or Target 2.

    Parameters
    ----------
    positions:
        List of enriched position dicts.
        Each dict must have: ticker, live_price, target_1 (optional),
        target_2 (optional).

    Returns
    -------
    Subset of positions that have reached a target.
    Each returned dict has an extra ``alert_type`` key:
    ``"TARGET_2"`` (highest priority) or ``"TARGET_1"``.
    """
    alerts: list[dict] = []
    for pos in positions:
        live = pos.get("live_price")
        t1 = pos.get("target_1")
        t2 = pos.get("target_2")
        if live is None:
            continue
        if t2 and live >= t2:
            alerts.append({**pos, "alert_type": "TARGET_2"})
        elif t1 and live >= t1:
            alerts.append({**pos, "alert_type": "TARGET_1"})
    return alerts


def get_all_alerts(positions: list[dict]) -> dict[str, list[dict]]:
    """
    Run all alert checks and return a combined dict.

    Returns
    -------
    Dict with keys ``"stop"`` and ``"target"``, each a list of alert dicts.
    """
    return {
        "stop": check_stop_alerts(positions),
        "target": check_target_alerts(positions),
    }


# ---------------------------------------------------------------------------
# Email notification (optional)
# ---------------------------------------------------------------------------

def send_alert_email(alerts: list[dict], alert_type: str = "STOP") -> bool:
    """
    Send an email notification for triggered alerts.

    Requires email credentials to be configured in ``config/email_config.py``.

    Parameters
    ----------
    alerts:
        List of alert dicts (output of ``check_stop_alerts`` or
        ``check_target_alerts``).
    alert_type:
        "STOP" or "TARGET" — used in the subject line.

    Returns
    -------
    True if the email was sent successfully, False otherwise.
    """
    if not alerts:
        return False
    try:
        from config.email_config import EMAIL_CONFIG
        from src.reports.email_sender import send_email

        subject = f"🚨 KešMani Alert — {alert_type} triggered on {len(alerts)} position(s)"
        lines: list[str] = [f"<h2>KešMani {alert_type} Alert</h2>", "<ul>"]
        for a in alerts:
            ticker = a.get("ticker", "?")
            live = a.get("live_price", "N/A")
            stop = a.get("stop_loss", "N/A")
            t1 = a.get("target_1", "N/A")
            if alert_type == "STOP":
                lines.append(f"<li><b>{ticker}</b>: live ${live} ≤ stop ${stop}</li>")
            else:
                lines.append(f"<li><b>{ticker}</b>: live ${live} ≥ target ${t1}</li>")
        lines.append("</ul>")
        body = "\n".join(lines)

        send_email(subject=subject, html_body=body)
        logger.info("Alert email sent: %s (%d positions)", alert_type, len(alerts))
        return True
    except Exception as exc:
        logger.warning("Alert email failed: %s", exc)
        return False
