import * as react from 'react';
import { DashboardSpec, PanelSpec, GraphResult, GraphNode, PanelResponse, Filter, Formato, ChartSpec, MetricResult } from '@yachaydeep-yd/analytics-contract';
export { ChartSpec, ChartType, Clase, DashboardSpec, Encoding, Filter, FilterOp, Formato, GraphEdge, GraphNode, GraphResult, Interactions, Measure, MetricQuery, MetricResult, MetricSpec, PanelResponse, PanelSpec, Shape, Truncation } from '@yachaydeep-yd/analytics-contract';
import * as _tanstack_react_query from '@tanstack/react-query';
import * as zustand from 'zustand';

interface DashboardProps {
    spec: DashboardSpec;
    /** Muestra la firma "Yachay Deep Analytics" (esquina inferior derecha).
     *  Por defecto true; ponlo en false en planes de pago. */
    attribution?: boolean;
    /** Tema del contenedor, para que la firma se lea bien. */
    attributionTheme?: "light" | "dark";
    /** Color de la franja de la firma. Por defecto adopta `--yd-accent` del host
     *  (o el cian de Analytics si no está definida). */
    attributionAccent?: string;
}
declare function Dashboard({ spec, attribution, attributionTheme, attributionAccent, }: DashboardProps): react.JSX.Element;

interface AttributionBadgeProps {
    /** Tema del contenedor donde se embebe. */
    theme?: "light" | "dark";
    /** Destino del enlace. */
    href?: string;
    /** Marca opcional (glifo/emoji) a la izquierda del texto. Hoy: emoji provisional. */
    mark?: string;
    /**
     * Color de la franja de acento. Por defecto adopta el color de la PÁGINA
     * ANFITRIONA vía la variable CSS `--yd-accent`; si esa variable no está
     * definida (uso standalone), cae al cian propio de Analytics. La app que
     * embebe puede pasar su color de marca aquí o definir `--yd-accent`.
     */
    accent?: string;
}
declare function AttributionBadge({ theme, href, mark, accent, }: AttributionBadgeProps): react.JSX.Element;
/** Color de producto de Analytics, exportado para reutilizar (franjas, acentos). */
declare const ANALYTICS_COLOR: {
    readonly base: "#0E9AB8";
    readonly dark: "#0B7C93";
    readonly light: "#3FC0DA";
};

declare function Panel({ spec }: {
    spec: PanelSpec;
}): react.JSX.Element | null;

interface NetworkViewProps {
    data: GraphResult;
    colorBy?: "cluster" | "overlay";
    /** clúster (comunidad) de un nodo → nombre + color. Por defecto usa node.group. */
    clusterOf?: (n: GraphNode) => {
        name: string;
        color: string;
    };
    /** valor numérico para el overlay continuo. Por defecto usa node.value. */
    overlayValue?: (n: GraphNode) => number;
    height?: number;
    onSelect?: (id: string | null) => void;
}
declare function NetworkView({ data, colorBy, clusterOf, overlayValue, height, onSelect, }: NetworkViewProps): react.JSX.Element;

interface ChoroplethProps {
    /** GeoJSON FeatureCollection; las features llevan properties.name. */
    geojson: any;
    /** Nombre con que se registra el mapa (único por app). */
    mapName?: string;
    /** Datos por región: { name: <properties.name>, value: number }. */
    data: {
        name: string;
        value: number;
    }[];
    height?: number;
    onSelect?: (name: string | null) => void;
}
declare function ChoroplethView({ geojson, mapName, data, height, onSelect }: ChoroplethProps): react.JSX.Element;

declare function useMetric(spec: PanelSpec): _tanstack_react_query.UseQueryResult<NoInfer<PanelResponse>, Error>;

interface AnalyticsClientConfig {
    /** URL base del API (sin barra final). Ej.: "https://analytics.yachaydeep.com". */
    apiBase?: string;
    /** API key; si se define, se envía como `X-API-Key`. */
    apiKey?: string;
    /** Cabeceras extra a fusionar en cada petición. */
    headers?: Record<string, string>;
    /** Política de credenciales del fetch. Por defecto: "include" sin apiKey (cookie
     *  de sesión de yd.auth), "omit" cuando hay apiKey (evita choques de CORS). */
    credentials?: RequestCredentials;
}
/** Configura el cliente (fusiona con lo previo). Idempotente. */
declare function configureAnalytics(cfg: AnalyticsClientConfig): void;
/** URL base efectiva. */
declare function analyticsBase(): string;
/** Cabeceras efectivas (Content-Type + API key + extras). */
declare function analyticsHeaders(): Record<string, string>;
/** Política de credenciales efectiva. */
declare function analyticsCredentials(): RequestCredentials;

interface FilterState {
    filters: Record<string, Filter>;
    set: (field: string, value: unknown, op?: Filter["op"]) => void;
    toggle: (field: string, value: unknown) => void;
    clear: (field?: string) => void;
    asArray: () => Filter[];
}
declare const useFilters: zustand.UseBoundStore<zustand.StoreApi<FilterState>>;

declare function fmt(value: number, formato: Formato): string;
declare function toEChartsOption(chart: ChartSpec, result: MetricResult): {
    grid: {
        left: number;
        right: number;
        top: number;
        bottom: number;
    };
    tooltip: {
        trigger: string;
        valueFormatter: (v: number) => string;
        position?: undefined;
        formatter?: undefined;
    };
    xAxis: {
        type: string;
        data: unknown[];
        axisLine: {
            lineStyle: {
                color: string;
            };
        };
        name?: undefined;
    };
    yAxis: {
        type: string;
        axisLabel: {
            formatter: (v: number) => string;
        };
        data?: undefined;
    };
    series: {
        type: string;
        smooth: boolean;
        areaStyle: {
            opacity: number;
        } | undefined;
        data: unknown[];
        itemStyle: {
            color: string;
        };
        lineStyle: {
            color: string;
            width: number;
        };
    }[];
    visualMap?: undefined;
    legend?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    grid: {
        left: number;
        right: number;
        top: number;
        bottom: number;
    };
    tooltip: {
        trigger: string;
        valueFormatter: (v: number) => string;
        position?: undefined;
        formatter?: undefined;
    };
    xAxis: {
        type: string;
        axisLabel: {
            formatter: (v: number) => string;
        };
    } | {
        type: string;
        data: unknown[];
    };
    yAxis: {
        type: string;
        axisLabel: {
            formatter: (v: number) => string;
        };
    } | {
        inverse: boolean;
        type: string;
        data: unknown[];
        axisLabel?: undefined;
    };
    series: {
        type: string;
        data: unknown[];
        itemStyle: {
            color: string;
            borderRadius: number[];
        };
    }[];
    visualMap?: undefined;
    legend?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    grid: {
        left: number;
        right: number;
        top: number;
        bottom: number;
    };
    tooltip: {
        position: string;
        valueFormatter: (v: number) => string;
        trigger?: undefined;
        formatter?: undefined;
    };
    xAxis: {
        type: string;
        data: string[];
        axisLine?: undefined;
        name?: undefined;
    };
    yAxis: {
        type: string;
        data: string[];
        axisLabel?: undefined;
    };
    visualMap: {
        min: number;
        max: number;
        calculable: boolean;
        orient: string;
        left: string;
        bottom: number;
        inRange: {
            color: string[];
        };
    };
    series: {
        type: string;
        data: unknown[][];
        label: {
            show: boolean;
            formatter: (p: any) => string;
        };
    }[];
    legend?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    tooltip: {
        trigger: string;
        formatter: (p: any) => string;
        valueFormatter?: undefined;
        position?: undefined;
    };
    legend: {
        bottom: number;
        top?: undefined;
    };
    series: {
        type: string;
        radius: string[];
        avoidLabelOverlap: boolean;
        itemStyle: {
            borderColor: string;
            borderWidth: number;
        };
        label: {
            color: string;
        };
        data: {
            name: unknown;
            value: unknown;
            itemStyle: {
                color: string;
            };
        }[];
    }[];
    grid?: undefined;
    xAxis?: undefined;
    yAxis?: undefined;
    visualMap?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    grid: {
        left: number;
        right: number;
        top: number;
        bottom: number;
    };
    legend: {
        top: number;
        bottom?: undefined;
    };
    tooltip: {
        trigger: string;
        valueFormatter: (v: number) => string;
        position?: undefined;
        formatter?: undefined;
    };
    xAxis: {
        type: string;
        data: unknown[];
        axisLine?: undefined;
        name?: undefined;
    };
    yAxis: {
        type: string;
        axisLabel: {
            formatter: (v: number) => string;
        };
        data?: undefined;
    };
    series: {
        type: string;
        stack: string;
        data: unknown[];
        itemStyle: {
            color: string;
            borderColor: string;
            borderWidth: number;
        };
    }[];
    visualMap?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    tooltip: {
        formatter: (p: any) => string;
        trigger?: undefined;
        valueFormatter?: undefined;
        position?: undefined;
    };
    series: {
        type: string;
        roam: boolean;
        nodeClick: boolean;
        breadcrumb: {
            show: boolean;
        };
        label: {
            color: string;
        };
        itemStyle: {
            gapWidth: number;
            borderColor: string;
        };
        data: {
            name: unknown;
            value: unknown;
            itemStyle: {
                color: string;
            };
        }[];
    }[];
    grid?: undefined;
    xAxis?: undefined;
    yAxis?: undefined;
    visualMap?: undefined;
    legend?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    grid: {
        left: number;
        right: number;
        top: number;
        bottom: number;
    };
    tooltip: {
        trigger: string;
        formatter: (p: any) => string;
        valueFormatter?: undefined;
        position?: undefined;
    };
    xAxis: {
        type: string;
        name: string;
        data?: undefined;
        axisLine?: undefined;
    };
    yAxis: {
        type: string;
        axisLabel: {
            formatter: (v: number) => string;
        };
        data?: undefined;
    };
    series: {
        type: string;
        symbolSize: number;
        itemStyle: {
            color: string;
            opacity: number;
        };
        data: unknown[][];
    }[];
    visualMap?: undefined;
    legend?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    grid: {
        left: number;
        right: number;
        top: number;
        bottom: number;
    };
    tooltip: {
        trigger: string;
        valueFormatter: (v: number) => string;
        position?: undefined;
        formatter?: undefined;
    };
    xAxis: {
        type: string;
        data: unknown[];
        axisLine?: undefined;
        name?: undefined;
    };
    yAxis: {
        type: string;
        axisLabel: {
            formatter: (v: number) => string;
        };
        data?: undefined;
    };
    series: {
        type: string;
        barWidth: string;
        data: unknown[];
        itemStyle: {
            color: string;
            borderColor: string;
            borderWidth: number;
        };
    }[];
    visualMap?: undefined;
    legend?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    tooltip: {
        trigger: string;
        formatter: (p: any) => string;
        valueFormatter?: undefined;
        position?: undefined;
    };
    series: {
        type: string;
        left: number;
        right: number;
        minSize: string;
        label: {
            position: string;
            color: string;
        };
        labelLine: {
            show: boolean;
        };
        itemStyle: {
            borderColor: string;
            borderWidth: number;
        };
        data: {
            name: unknown;
            value: unknown;
            itemStyle: {
                color: string;
            };
        }[];
    }[];
    grid?: undefined;
    xAxis?: undefined;
    yAxis?: undefined;
    visualMap?: undefined;
    legend?: undefined;
    _table?: undefined;
    columns?: undefined;
    rows?: undefined;
} | {
    _table: boolean;
    columns: string[];
    rows: Record<string, unknown>[];
    grid?: undefined;
    tooltip?: undefined;
    xAxis?: undefined;
    yAxis?: undefined;
    series?: undefined;
    visualMap?: undefined;
    legend?: undefined;
};

declare function toCSV(result: MetricResult): string;
declare function exportCSV(result: MetricResult, filename?: string): void;
/** PNG desde una instancia de ECharts (chart.getDataURL). */
declare function exportPNG(chart: {
    getDataURL: (o?: any) => string;
}, filename?: string): void;

type Mode = "light" | "dark";
/** Paleta categórica validada (identidad de serie). Orden FIJO, nunca ciclado. */
declare const CATEGORICAL: Record<Mode, string[]>;
/** Tope de series para gráficos de todos-los-pares (scatter, burbuja, mapa). */
declare const ALL_PAIRS_CAP = 3;
/** Rampa secuencial (magnitud): un solo tono, claro→oscuro. Heatmaps, coropléticos. */
declare const SEQUENTIAL: string[];
/** Diverging: dos polos + gris neutro al centro. */
declare const DIVERGING: {
    low: string;
    mid: {
        light: string;
        dark: string;
    };
    high: string;
};
/** Estados (reservados; nunca como "serie 4"; van con icono + etiqueta). */
declare const STATUS: {
    good: string;
    warning: string;
    serious: string;
    critical: string;
};
/** Cromo e ink del gráfico por modo. */
declare const CHROME: Record<Mode, {
    surface: string;
    page: string;
    ink: string;
    ink2: string;
    muted: string;
    grid: string;
    axis: string;
}>;
/** Color primario del PRODUCTO (serie única, KPIs). Se sobreescribe por marca:
    Áncora ámbar, Kullki verde, Core dorado. Aquí el navy institucional por defecto. */
declare const PRODUCT_PRIMARY: {
    light: string;
    dark: string;
    accent: string;
};
declare function categorical(mode?: Mode): string[];
declare function seriesColor(i: number, mode?: Mode): string;

declare const palette_ALL_PAIRS_CAP: typeof ALL_PAIRS_CAP;
declare const palette_CATEGORICAL: typeof CATEGORICAL;
declare const palette_CHROME: typeof CHROME;
declare const palette_DIVERGING: typeof DIVERGING;
type palette_Mode = Mode;
declare const palette_PRODUCT_PRIMARY: typeof PRODUCT_PRIMARY;
declare const palette_SEQUENTIAL: typeof SEQUENTIAL;
declare const palette_STATUS: typeof STATUS;
declare const palette_categorical: typeof categorical;
declare const palette_seriesColor: typeof seriesColor;
declare namespace palette {
  export { palette_ALL_PAIRS_CAP as ALL_PAIRS_CAP, palette_CATEGORICAL as CATEGORICAL, palette_CHROME as CHROME, palette_DIVERGING as DIVERGING, type palette_Mode as Mode, palette_PRODUCT_PRIMARY as PRODUCT_PRIMARY, palette_SEQUENTIAL as SEQUENTIAL, palette_STATUS as STATUS, palette_categorical as categorical, palette_seriesColor as seriesColor };
}

declare function money(value: number): string;
declare function number(value: number, decimals?: number): string;
declare function percent(value: number, decimals?: number): string;
declare function impact(value: number): string;

declare const format_impact: typeof impact;
declare const format_money: typeof money;
declare const format_number: typeof number;
declare const format_percent: typeof percent;
declare namespace format {
  export { format_impact as impact, format_money as money, format_number as number, format_percent as percent };
}

export { ANALYTICS_COLOR, type AnalyticsClientConfig, AttributionBadge, type AttributionBadgeProps, type ChoroplethProps, ChoroplethView, Dashboard, type DashboardProps, NetworkView, type NetworkViewProps, Panel, analyticsBase, analyticsCredentials, analyticsHeaders, configureAnalytics, exportCSV, exportPNG, fmt, format, palette, toCSV, toEChartsOption, useFilters, useMetric };
