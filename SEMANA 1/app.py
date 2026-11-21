from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.ticker import FuncFormatter


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "ventas_mensuales_tratada.csv"
if not DATA_FILE.exists():
    DATA_FILE = BASE_DIR / "SEMANA 1" / "ventas_mensuales.csv"

REQUIRED_COLUMNS = {
    "periodo",
    "anio",
    "mes",
    "region",
    "sucursal",
    "categoria",
    "producto",
    "laboratorio",
    "cantidad",
    "precio",
    "descuento_pct",
    "ventas",
}

st.set_page_config(
    page_title="Panel de análisis de ventas",
    page_icon="📊",
    layout="wide",
)


@st.cache_data
def load_sales(path: str) -> pd.DataFrame:
    data = pd.read_csv(path, encoding="utf-8-sig")
    missing_columns = REQUIRED_COLUMNS - set(data.columns)
    if missing_columns:
        raise ValueError(
            "Faltan columnas requeridas en la base: "
            + ", ".join(sorted(missing_columns))
        )

    data["periodo"] = data["periodo"].astype("string").str.strip()
    data["region"] = data["region"].astype("string").str.strip()
    data["sucursal"] = data["sucursal"].astype("string").str.strip()
    data["categoria"] = data["categoria"].astype("string").str.strip()
    data["producto"] = data["producto"].astype("string").str.strip()
    data["laboratorio"] = data["laboratorio"].astype("string").str.strip()

    for column in ("anio", "mes", "cantidad", "precio", "descuento_pct", "ventas"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    invalid_period = pd.to_datetime(data["periodo"] + "-01", errors="coerce").isna()
    if invalid_period.any():
        raise ValueError(f"Hay {int(invalid_period.sum())} registros con periodo inválido.")

    required_values = ["anio", "mes", "cantidad", "precio", "descuento_pct", "ventas"]
    missing_values = int(data[required_values].isna().sum().sum())
    if missing_values:
        raise ValueError(
            f"Hay {missing_values} valores numéricos vacíos o inválidos en la base."
        )

    data["anio"] = data["anio"].astype(int)
    data["mes"] = data["mes"].astype(int)
    return data


def money_axis(value: float, _: int) -> str:
    return f"{value:,.0f}"


def render_sales_chart(frame: pd.DataFrame, title: str) -> None:
    figure, axis = plt.subplots(figsize=(12, 4.5))
    axis.plot(frame["periodo"], frame["ventas"], marker="o", color="#2364AA")
    axis.set_title(title)
    axis.set_ylabel("Ventas")
    axis.yaxis.set_major_formatter(FuncFormatter(money_axis))
    axis.tick_params(axis="x", rotation=55)
    axis.grid(alpha=0.25)
    figure.tight_layout()
    st.pyplot(figure, clear_figure=True)
    plt.close(figure)


def render_growth_chart(
    frame: pd.DataFrame,
    metric: str,
    title: str,
    axis_label: str,
) -> None:
    figure, axis = plt.subplots(figsize=(13, 5))
    growth = frame[metric].dropna()
    colors = ["#2A9D8F" if value >= 0 else "#E76F51" for value in growth]
    axis.plot(growth.index, growth.values, color="#526D82", linewidth=1.5)
    axis.scatter(growth.index, growth.values, c=colors, s=48, zorder=3)
    axis.axhline(0, color="black", linewidth=1, alpha=0.6)
    axis.set_title(title)
    axis.set_ylabel(axis_label)
    axis.tick_params(axis="x", rotation=55)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    st.pyplot(figure, clear_figure=True)
    plt.close(figure)


try:
    df = load_sales(str(DATA_FILE))
except FileNotFoundError as error:
    st.error(f"No se encontró el archivo de ventas: {DATA_FILE}")
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()

st.title("Panel interactivo de ventas")
st.caption(
    f"Fuente: `{DATA_FILE.name}` · {len(df):,} registros · "
    f"periodo {df['periodo'].min()} a {df['periodo'].max()}"
)

with st.sidebar:
    st.header("Filtros")
    all_years = sorted(df["anio"].unique().tolist())
    selected_years = st.multiselect("Años", all_years, default=all_years)
    selected_regions = st.multiselect(
        "Regiones",
        sorted(df["region"].dropna().unique().tolist()),
        default=sorted(df["region"].dropna().unique().tolist()),
    )
    selected_categories = st.multiselect(
        "Categorías",
        sorted(df["categoria"].dropna().unique().tolist()),
    )
    selected_branches = st.multiselect(
        "Sucursales",
        sorted(df["sucursal"].dropna().unique().tolist()),
    )

if not selected_years or not selected_regions:
    st.info("Selecciona al menos un año y una región en los filtros.")
    st.stop()

segment = df[df["region"].isin(selected_regions)]
if selected_categories:
    segment = segment[segment["categoria"].isin(selected_categories)]
if selected_branches:
    segment = segment[segment["sucursal"].isin(selected_branches)]

filtered = segment[segment["anio"].isin(selected_years)].copy()
if filtered.empty:
    st.warning("No hay registros con la combinación de filtros seleccionada.")
    st.stop()

tabs = st.tabs(
    [
        "Resumen",
        "Crecimiento",
        "Regiones",
        "Sucursales",
        "Productos y categorías",
        "Explorar datos",
    ]
)

with tabs[0]:
    st.subheader("Indicadores generales")
    total_sales = filtered["ventas"].sum()
    total_units = filtered["cantidad"].sum()
    columns = st.columns(5)
    columns[0].metric("Ventas", f"{total_sales:,.2f}")
    columns[1].metric("Unidades vendidas", f"{total_units:,.2f}")
    columns[2].metric("Registros", f"{len(filtered):,}")
    columns[3].metric("Sucursales", f"{filtered['sucursal'].nunique():,}")
    columns[4].metric(
        "Descuento promedio",
        f"{filtered['descuento_pct'].mean() * 100:.2f}%",
    )

    monthly_filtered = (
        filtered.groupby("periodo", as_index=False)
        .agg(ventas=("ventas", "sum"), cantidad=("cantidad", "sum"))
        .sort_values("periodo")
    )
    render_sales_chart(monthly_filtered, "Ventas mensuales")

    left, right = st.columns(2)
    with left:
        category_sales = (
            filtered.groupby("categoria", as_index=False)["ventas"]
            .sum()
            .sort_values("ventas", ascending=True)
        )
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.barh(category_sales["categoria"], category_sales["ventas"], color="#3DA5D9")
        axis.set_title("Ventas por categoría")
        axis.xaxis.set_major_formatter(FuncFormatter(money_axis))
        axis.grid(axis="x", alpha=0.2)
        figure.tight_layout()
        st.pyplot(figure, clear_figure=True)
        plt.close(figure)

    with right:
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.hist(filtered["ventas"], bins=35, color="#73BFB8", edgecolor="white")
        axis.set_title("Distribución de ventas por registro")
        axis.set_xlabel("Ventas")
        axis.set_ylabel("Frecuencia")
        axis.grid(axis="y", alpha=0.2)
        figure.tight_layout()
        st.pyplot(figure, clear_figure=True)
        plt.close(figure)

with tabs[1]:
    st.subheader("Crecimiento mensual y anual")
    monthly_segment = (
        segment.groupby("periodo", as_index=False)
        .agg(ventas=("ventas", "sum"), unidades=("cantidad", "sum"))
        .sort_values("periodo")
    )
    monthly_segment["crecimiento_ventas_pct"] = (
        monthly_segment["ventas"].pct_change() * 100
    )
    monthly_segment["crecimiento_unidades_pct"] = (
        monthly_segment["unidades"].pct_change() * 100
    )
    monthly_selected = monthly_segment[
        monthly_segment["periodo"].str[:4].astype(int).isin(selected_years)
    ].copy()

    render_growth_chart(
        monthly_selected.set_index("periodo"),
        "crecimiento_ventas_pct",
        "Crecimiento mensual de ventas",
        "Cambio frente al mes anterior (%)",
    )
    render_growth_chart(
        monthly_selected.set_index("periodo"),
        "crecimiento_unidades_pct",
        "Crecimiento mensual de unidades vendidas",
        "Cambio frente al mes anterior (%)",
    )
    st.caption(
        "La primera tasa visible puede usar el mes previo aunque este no esté "
        "seleccionado. El primer mes disponible de la base no tiene comparación."
    )

    annual = (
        filtered.groupby("anio", as_index=False)
        .agg(ventas=("ventas", "sum"), unidades=("cantidad", "sum"))
        .sort_values("anio")
    )
    if not annual.empty:
        annual["crecimiento_ventas_pct"] = annual["ventas"].pct_change() * 100
        annual["crecimiento_unidades_pct"] = annual["unidades"].pct_change() * 100
        st.dataframe(
            annual.rename(
                columns={
                    "anio": "Año",
                    "ventas": "Ventas totales",
                    "unidades": "Unidades vendidas",
                    "crecimiento_ventas_pct": "Crecimiento ventas (%)",
                    "crecimiento_unidades_pct": "Crecimiento unidades (%)",
                }
            ).style.format(
                {
                    "Ventas totales": "{:,.2f}",
                    "Unidades vendidas": "{:,.2f}",
                    "Crecimiento ventas (%)": "{:+.2f}",
                    "Crecimiento unidades (%)": "{:+.2f}",
                }
            ),
            width="stretch",
        )

        if {2024, 2025}.issubset(set(annual["anio"])):
            year_sales = annual.set_index("anio")["ventas"]
            year_units = annual.set_index("anio")["unidades"]
            sales_growth = (year_sales.loc[2025] / year_sales.loc[2024] - 1) * 100
            units_growth = (year_units.loc[2025] / year_units.loc[2024] - 1) * 100
            cols = st.columns(2)
            cols[0].metric(
                "Crecimiento anual de ventas (2025 vs. 2024)",
                f"{sales_growth:+.2f}%",
                f"{year_sales.loc[2025] - year_sales.loc[2024]:+,.2f}",
            )
            cols[1].metric(
                "Crecimiento anual de unidades (2025 vs. 2024)",
                f"{units_growth:+.2f}%",
                f"{year_units.loc[2025] - year_units.loc[2024]:+,.2f} unidades",
            )

with tabs[2]:
    st.subheader("Desempeño por región")
    recent_months = sorted(filtered["periodo"].unique())[-12:]
    recent = filtered[filtered["periodo"].isin(recent_months)]
    region_summary = (
        recent.groupby("region", as_index=False)
        .agg(ventas_12_meses=("ventas", "sum"), unidades=("cantidad", "sum"))
        .sort_values("ventas_12_meses", ascending=False)
    )
    if not region_summary.empty:
        region_summary["participacion_pct"] = (
            region_summary["ventas_12_meses"]
            / region_summary["ventas_12_meses"].sum()
            * 100
        )
        region_summary["promedio_mensual"] = (
            region_summary["ventas_12_meses"] / len(recent_months)
        )

        monthly_region = (
            recent.groupby(["periodo", "region"], as_index=False)["ventas"]
            .sum()
            .pivot(index="periodo", columns="region", values="ventas")
            .fillna(0)
        )
        st.line_chart(monthly_region, width="stretch")
        st.dataframe(
            region_summary.rename(
                columns={
                    "region": "Región",
                    "ventas_12_meses": "Ventas del periodo",
                    "unidades": "Unidades",
                    "participacion_pct": "Participación (%)",
                    "promedio_mensual": "Promedio mensual",
                }
            ).style.format(
                {
                    "Ventas del periodo": "{:,.2f}",
                    "Unidades": "{:,.2f}",
                    "Participación (%)": "{:.2f}",
                    "Promedio mensual": "{:,.2f}",
                }
            ),
            width="stretch",
        )
        st.caption(
            f"Se muestran los últimos {len(recent_months)} meses disponibles "
            f"bajo los filtros: {recent_months[0]} a {recent_months[-1]}."
        )

with tabs[3]:
    st.subheader("Desempeño por sucursal")
    branch_sales = (
        filtered.groupby("sucursal", as_index=False)
        .agg(ventas=("ventas", "sum"), unidades=("cantidad", "sum"))
        .sort_values("ventas", ascending=False)
    )
    top_branches = branch_sales.head(20).sort_values("ventas")
    figure, axis = plt.subplots(figsize=(10, 8))
    axis.barh(top_branches["sucursal"], top_branches["ventas"], color="#2364AA")
    axis.set_title("20 sucursales con mayores ventas")
    axis.xaxis.set_major_formatter(FuncFormatter(money_axis))
    axis.grid(axis="x", alpha=0.2)
    figure.tight_layout()
    st.pyplot(figure, clear_figure=True)
    plt.close(figure)

    st.markdown("#### Sucursales con mayor descuento promedio")
    discount_ranking = (
        filtered.groupby("sucursal", as_index=False)
        .agg(
            descuento_promedio=("descuento_pct", "mean"),
            registros=("descuento_pct", "size"),
            ventas=("ventas", "sum"),
        )
        .sort_values("descuento_promedio", ascending=False)
        .head(10)
    )
    discount_ranking["descuento_promedio"] *= 100
    figure, axis = plt.subplots(figsize=(10, 5))
    ranked_discount = discount_ranking.sort_values("descuento_promedio")
    axis.barh(
        ranked_discount["sucursal"],
        ranked_discount["descuento_promedio"],
        color="#6A4C93",
    )
    axis.set_xlabel("Descuento promedio (%)")
    axis.set_title("Top 10 sucursales por descuento promedio")
    axis.grid(axis="x", alpha=0.2)
    figure.tight_layout()
    st.pyplot(figure, clear_figure=True)
    plt.close(figure)
    st.dataframe(
        discount_ranking.rename(
            columns={
                "sucursal": "Sucursal",
                "descuento_promedio": "Descuento promedio (%)",
                "registros": "Registros",
                "ventas": "Ventas",
            }
        ).style.format(
            {
                "Descuento promedio (%)": "{:.2f}",
                "Ventas": "{:,.2f}",
            }
        ),
        width="stretch",
    )

    st.markdown("#### Sucursales nuevas y antiguas")
    first_months = df.groupby("sucursal")["periodo"].min()
    cutoff = "2025-06"
    branch_sales["primera_venta_observada"] = branch_sales["sucursal"].map(first_months)
    branch_sales["grupo"] = branch_sales["primera_venta_observada"].map(
        lambda month: "Nueva" if month >= cutoff else "Antigua"
    )
    branch_monthly = (
        filtered.groupby(["sucursal", "periodo"], as_index=False)
        .agg(ventas=("ventas", "sum"))
    )
    branch_group_map = branch_sales.set_index("sucursal")["grupo"]
    branch_monthly["grupo"] = branch_monthly["sucursal"].map(branch_group_map)
    branch_summary = (
        branch_monthly.groupby("grupo", as_index=False)
        .agg(
            sucursales=("sucursal", "nunique"),
            ventas=("ventas", "sum"),
            sucursal_meses_activos=("periodo", "count"),
        )
    )
    branch_summary["ventas_promedio_sucursal_mes_activo"] = (
        branch_summary["ventas"] / branch_summary["sucursal_meses_activos"]
    )
    st.dataframe(branch_summary, width="stretch")
    st.caption(
        "Nueva = primera venta observada desde junio de 2025. "
        "Es una aproximación; la base no contiene fechas de apertura."
    )
    new_branch_list = branch_sales[branch_sales["grupo"] == "Nueva"][
        ["sucursal", "primera_venta_observada", "ventas"]
    ]
    if not new_branch_list.empty:
        st.dataframe(new_branch_list, width="stretch")

with tabs[4]:
    st.subheader("Productos, categorías y laboratorios")
    for title, column in (
        ("Categorías por ventas", "categoria"),
        ("Productos por ventas", "producto"),
        ("Laboratorios por ventas", "laboratorio"),
    ):
        st.markdown(f"#### {title}")
        grouped = (
            filtered.groupby(column, as_index=False)
            .agg(ventas=("ventas", "sum"), unidades=("cantidad", "sum"))
            .sort_values("ventas", ascending=False)
            .head(15)
        )
        st.dataframe(
            grouped.rename(
                columns={
                    column: title.split(" ")[0],
                    "ventas": "Ventas",
                    "unidades": "Unidades",
                }
            ).style.format({"Ventas": "{:,.2f}", "Unidades": "{:,.2f}"}),
            width="stretch",
        )

    st.markdown("#### Relaciones con ventas")
    scatter_columns = st.columns(3)
    for column, title, x_label in (
        ("cantidad", "Cantidad y ventas", "Cantidad"),
        ("precio", "Precio y ventas", "Precio"),
        ("descuento_pct", "Descuento y ventas", "Descuento (%)"),
    ):
        correlation = filtered[column].corr(filtered["ventas"])
        chart_data = filtered[[column, "ventas"]].sample(
            min(3000, len(filtered)),
            random_state=1,
        ).copy()
        if column == "descuento_pct":
            chart_data[column] *= 100
        figure, axis = plt.subplots(figsize=(5, 3.5))
        axis.scatter(chart_data[column], chart_data["ventas"], alpha=0.3, s=12)
        axis.set_title(f"{title} (r={correlation:.3f})")
        axis.set_xlabel(x_label)
        axis.set_ylabel("Ventas")
        axis.grid(alpha=0.2)
        figure.tight_layout()
        with scatter_columns[
            ("cantidad", "precio", "descuento_pct").index(column)
        ]:
            st.pyplot(figure, clear_figure=True)
        plt.close(figure)
    st.caption("La correlación describe asociación lineal y no implica causalidad.")

with tabs[5]:
    st.subheader("Explorar los datos filtrados")
    st.write(f"Dimensiones: **{len(filtered):,} filas × {filtered.shape[1]} columnas**")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Tipos de datos")
        st.dataframe(
            pd.DataFrame(
                {
                    "Columna": filtered.columns,
                    "Tipo": [str(dtype) for dtype in filtered.dtypes],
                }
            ),
            width="stretch",
            hide_index=True,
        )
    with right:
        st.markdown("#### Valores ausentes")
        missing = filtered.isna().sum().rename("Valores ausentes").to_frame()
        st.dataframe(missing, width="stretch")

    st.markdown("#### Resumen de variables numéricas")
    st.dataframe(
        filtered[
            ["anio", "mes", "cantidad", "precio", "descuento_pct", "ventas"]
        ].describe().T,
        width="stretch",
    )
    st.markdown("#### Muestra de registros")
    st.dataframe(filtered.head(100), width="stretch")
    st.download_button(
        "Descargar datos filtrados (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="ventas_filtradas.csv",
        mime="text/csv",
    )

st.sidebar.caption("Panel local: los datos no se envían a un servicio externo.")
