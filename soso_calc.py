import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Dados confirmados ──────────────────────────────────────────────────────────
SOSO_TOTAL        = 150_000_000   # tokens liberados para airdrop (temporada 1)
SOPOINTS_TOTAL    = 25_000_000    # estimativa total plataforma (semanas 1-15)
SOSO_PRICE        = 0.40          # preco atual SOSO em USD

user_pts          = 2_549         # seus SoPoints atuais
user_pts_5k       = 5_000
user_pts_10k      = 10_000

# ── Formula pro-rata (confirmada) ─────────────────────────────────────────────
# SOSO_usuario = (sopoints_usuario / sopoints_total) * 150_000_000
ratio = SOSO_TOTAL / SOPOINTS_TOTAL  # SOSO por SoPoint

soso_now  = user_pts   / SOPOINTS_TOTAL * SOSO_TOTAL
soso_5k   = user_pts_5k  / SOPOINTS_TOTAL * SOSO_TOTAL
soso_10k  = user_pts_10k / SOPOINTS_TOTAL * SOSO_TOTAL

# ── Comparacao 1:1 vs pro-rata ─────────────────────────────────────────────────
print("=" * 65)
print("  CONVERSAO SOPOINTS -> SOSO  |  Formula Pro-Rata Confirmada")
print("=" * 65)
print()
print(f"  Airdrop total      : 150,000,000 SOSO")
print(f"  Total plataforma   : ~25,000,000 SoPoints (est. semanas 1-15)")
print(f"  Ratio implicito    : {ratio:.2f} SOSO por SoPoint")
print(f"  Preco SOSO         : USD {SOSO_PRICE:.2f}")
print()
print(f"  FORMULA: SOSO = (seus_pts / 25M) x 150M")
print()

print("  " + "-" * 60)
print(f"  {'Cenario':<22} {'SoPoints':>10} {'SOSO':>12} {'USD (0.40)':>12}")
print("  " + "-" * 60)

cenarios = [
    ("Voce HOJE",           user_pts,    soso_now),
    ("Se chegar 5k",        user_pts_5k, soso_5k),
    ("Diamond (10k)",       user_pts_10k,soso_10k),
    ("Hipotetico 1:1 hoje", user_pts,    user_pts),   # referencia
]
for label, pts, soso in cenarios:
    usd = soso * SOSO_PRICE
    marker = "  <- ATUAL" if pts == user_pts and soso != user_pts else ""
    marker = "  <- (hipotetico)" if soso == user_pts else marker
    print(f"  {label:<22} {pts:>10,} {soso:>12,.0f} {usd:>11,.0f}{marker}")

print()
print("  DIFERENCA: pro-rata MELHOR que 1:1")
print(f"    1:1 hoje   : {user_pts:,} SOSO = USD {user_pts * SOSO_PRICE:,.0f}")
print(f"    Pro-rata   : {soso_now:,.0f} SOSO = USD {soso_now * SOSO_PRICE:,.0f}")
print(f"    Multiplicador: {soso_now / user_pts:.1f}x mais SOSO do que 1:1")

print()
print("=" * 65)
print("  PROJECOES POR TOTAL DE SOPOINTS DA PLATAFORMA")
print("=" * 65)
print()
print(f"  Seus pontos atuais: {user_pts:,} SoPoints")
print()
print(f"  {'Total Plataforma':>18} {'Ratio':>8} {'Seus SOSO':>12} {'USD (0.40)':>12}")
print("  " + "-" * 55)
for total in [10_000_000, 20_000_000, 25_000_000, 30_000_000, 50_000_000]:
    r = SOSO_TOTAL / total
    s = user_pts / total * SOSO_TOTAL
    u = s * SOSO_PRICE
    mark = "  <- est. atual" if total == 25_000_000 else ""
    print(f"  {total:>18,} {r:>7.1f}x {s:>12,.0f} {u:>11,.0f}{mark}")

print()
print("=" * 65)
print("  PROJECOES SE VOCE CHEGAR A 5K / 10K SOPOINTS")
print("=" * 65)
print()
for pts_label, pts_val in [("5,000 pts", user_pts_5k), ("10,000 pts (Diamond)", user_pts_10k)]:
    soso_val = pts_val / SOPOINTS_TOTAL * SOSO_TOTAL
    usd_val  = soso_val * SOSO_PRICE
    print(f"  {pts_label}:")
    print(f"    SOSO recebidos : {soso_val:>12,.0f}")
    print(f"    Valor USD 0.40 : USD {usd_val:>10,.0f}")
    for price in [0.10, 0.40, 1.00, 2.00, 5.00]:
        print(f"      @ USD {price:.2f}/SOSO : USD {soso_val * price:>10,.0f}")
    print()

print("=" * 65)
print("  CONCLUSAO")
print("=" * 65)
print(f"""
  Pro-rata NAO e 1:1 — e MELHOR para voce:
  - 1:1 daria apenas {user_pts:,} SOSO = USD {user_pts*0.40:,.0f}
  - Pro-rata da {soso_now:,.0f} SOSO = USD {soso_now*0.40:,.0f}  ({soso_now/user_pts:.1f}x mais)

  Por que pro-rata e melhor?
  - 150M SOSO / 25M total pts = 6 SOSO por ponto (nao 1)
  - Quem acumula pontos ANTES do rush final leva vantagem
  - Se a plataforma explodir (50M pts), seu ratio cai para 3x

  Proximo passo:
  - Continuar farmando ate 5k pts (mais USD {(soso_5k-soso_now)*0.40:,.0f} potencial)
  - Diamond 10k pts vale USD {soso_10k*0.40:,.0f} ao preco atual de 0.40
""")
