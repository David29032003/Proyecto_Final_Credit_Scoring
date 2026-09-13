"""Diagrama del ciclo de crédito end-to-end (sección 6.1)."""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# Colores: texto, superficie y acentos.
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
SURFACE, BORDER = "#fcfcfb", "#c3c2b7"
BLUE, BLUE_LIGHT, ORANGE = "#2a78d6", "#cde2fb", "#eb6834"

CREDIT_CYCLE_STEPS = [
    # (etapa macro, título, detalle)
    ("ORIGINACIÓN", "1. Solicitud", "web · app · agencia · alianza\nasesor de campo con tablet\nmonto, plazo, destino, ingreso"),
    ("ORIGINACIÓN", "2. Validaciones", "KYC biométrico (RENIEC)\nAML/PEP · fraude · duplicados\nelegibilidad · mora vigente"),
    ("EVALUACIÓN", "3. Fuentes de datos", "buró en T0 · core/CRM\ngeocodificación (distancia)\ndeclarados + visita de campo"),
    ("EVALUACIÓN", "4. Cálculo de variables", "DTI post-crédito · faltantes\nimputación\nmisma lógica que en desarrollo"),
    ("EVALUACIÓN", "5. Scoring PD", "PD 12m → score → banda\nreason codes\nAPI síncrona (< 1 s)"),
    ("DECISIÓN", "6. Reglas de política", "capacidad: DTI post\nmonto · thin-file · alianza\nlímites de concentración"),
    ("DECISIÓN", "7. Decisión", "APPROVE (automático)\nREVIEW → analista/comité\nREJECT + motivo"),
    ("DECISIÓN", "8. Pricing y monto", "tasa por banda (cubre EL)\nmonto máx. por capacidad\ncalendario según ciclo productivo"),
    ("DESEMBOLSO", "9. Desembolso", "firma digital · biometría\ncuenta / billetera / agente\nchecklist antifraude"),
    ("MONITOREO", "10. Seguimiento", "alertas mora temprana\nKRIs por zona y cosecha\nPSI · calibración · EL"),
    ("COBRANZA", "11. Cobranza", "preventiva (antes de cuota)\nreprogramación por clima\nrecuperación → LGD"),
    ("MONITOREO", "12. Retroalimentación", "outcome 12m → datamart\noverrides y REVIEW registrados\nrecalibrar / reentrenar"),
]
MODEL_STEP = 5


def plot_credit_cycle(path=None, dpi=150):
    """Flujo end-to-end en serpentina: pasos 1-6 izq->der, 7-12 der->izq."""
    w, h, dx = 2.45, 1.62, 2.85
    y_top, y_bot = 3.05, 0.4
    pos = {}
    for i in range(6):
        pos[i + 1] = (i * dx, y_top)
        pos[12 - i] = (i * dx, y_bot)

    fig, ax = plt.subplots(figsize=(17, 6.6))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for n, (stage, title, detail) in enumerate(CREDIT_CYCLE_STEPS, start=1):
        x, y = pos[n]
        is_model = n == MODEL_STEP
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                             fc=BLUE_LIGHT if is_model else SURFACE,
                             ec=BLUE if is_model else BORDER, lw=2.0 if is_model else 1.0)
        ax.add_patch(box)
        ax.text(x + 0.14, y + h - 0.2, stage, fontsize=8, color=MUTED, fontweight="bold", va="top")
        ax.text(x + 0.14, y + h - 0.44, title, fontsize=11.5, color=INK, fontweight="bold", va="top")
        ax.text(x + 0.14, y + h - 0.8, detail, fontsize=9, color=INK_2, va="top", linespacing=1.45)

    def arrow(p0, p1, color=INK_2, style="-|>", lw=1.2, cs="arc3"):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13, color=color, lw=lw,
                                     connectionstyle=cs, shrinkA=0, shrinkB=0))

    gap = dx - w
    for i in range(1, 6):          # fila superior
        x, y = pos[i]
        arrow((x + w + 0.04, y + h / 2), (x + dx - 0.04, y + h / 2))
    x6, _ = pos[6]                  # bajada 6 → 7
    arrow((x6 + w / 2, y_top - 0.04), (x6 + w / 2, y_bot + h + 0.04))
    for i in range(7, 12):         # fila inferior (der → izq)
        x, y = pos[i]
        arrow((x - 0.04, y + h / 2), (x - gap + 0.04, y + h / 2))

    # Lazo de retroalimentación 12 → 3 (datos) y 5 (modelo) por el corredor central.
    x12, _ = pos[12]
    y_mid = (y_bot + h + y_top) / 2
    xs = x12 + w / 2
    ax.plot([xs, xs], [y_bot + h + 0.04, y_mid], color=ORANGE, lw=1.6)
    ax.plot([xs, pos[5][0] + w / 2], [y_mid, y_mid], color=ORANGE, lw=1.6)
    for target in (3, 5):
        xt = pos[target][0] + w / 2
        arrow((xt, y_mid), (xt, y_top - 0.04), color=ORANGE, lw=1.6)
    ax.text(xs + 0.12, y_mid - 0.1,
            "Retroalimentación: performance 12m, overrides y resultados de REVIEW → datamart, monitoreo y recalibración",
            fontsize=9, color=INK_2, va="top")

    xm, ym = pos[MODEL_STEP]
    ax.text(xm + w / 2, ym + h + 0.18, "Punto de consumo del modelo PD", ha="center", fontsize=9.5,
            color=INK, fontweight="bold")

    ax.set_xlim(-0.2, 5 * dx + w + 0.2)
    ax.set_ylim(y_bot - 0.3, y_top + h + 0.55)
    ax.axis("off")
    fig.tight_layout()
    if path is not None:
        fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=SURFACE)
    return fig
