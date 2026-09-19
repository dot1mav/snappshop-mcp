/**
 * snappshop-arvan-unified.js
 * Unified ArvanCloud Edge MCP Server
 * 
 * This file combines Normalization, API transport, and MCP Protocol
 * into a single file for easy deployment to ArvanCloud Edge.
 */

// --- 1. Configuration & Constants ---
const API_BASE = "https://apix.snappshop.ir";
const WEB_BASE_URL = "https://snappshop.ir";
const GEO = "?lat=35.77331&lng=51.418591";
const IR_TOMAN_PER_RIAL = 10;

// --- 2. Normalization Layer (Mirror of snappshop/normalize.py) ---
const formatToman = (toman) => {
    if (toman == null) return null;
    return new Intl.NumberFormat("en-US").format(Math.round(toman)) + " تومان";
};

const priceBlock = (toman, originalToman = null, discountPercent = null) => {
    const t = toman ? Math.round(toman) : null;
    const o = (originalToman && originalToman !== 0) ? Math.round(originalToman) : null;
    return {
        toman: t,
        rial: t ? t * IR_TOMAN_PER_RIAL : null,
        display: formatToman(t),
        original_toman: o,
        original_rial: o ? o * IR_TOMAN_PER_RIAL : null,
        original_display: formatToman(o),
        discount_percent: discountPercent,
        currency: "IRT",
    };
};

const normalizeCard = (item) => {
    if (!item) return {};
    const priceRaw = item.price || {};
    const special = priceRaw.discounted_price || null;
    const original = priceRaw.price || null;
    const price = (special && original && special < original) 
        ? priceBlock(special, original, priceRaw.discount) 
        : priceBlock(original || special);

    return {
        product_id: item.id,
        slug: item.href ? item.href.split("/").pop() : null,
        product_url: item.href ? (item.href.startsWith("http") ? item.href : WEB_BASE_URL + item.href) : null,
        title: item.title ? item.title.trim() : null,
        image_url: item.image?.src,
        price: price,
        rating: { value: item.state?.rate, count: item.state?.rate_count }
    };
};

const normalizeSearch = (payload, { query, limit = 10 }) => {
    const structure = payload?.data?.structure || [];
    const products = [];
    const seen = new Set();

    for (const sec of structure) {
        for (const item of (sec.items || [])) {
            const card = normalizeCard(item);
            if (card.slug && !seen.has(card.slug)) {
                seen.add(card.slug);
                products.push(card);
            }
        }
    }
    const sliced = products.slice(0, limit);
    return { query, count: sliced.length, products: sliced };
};

const normalizeProduct = (payload, { product_id }) => {
    const data = payload?.data || {};
    const content = data.content || {};
    const bestOffer = (data.variants || []).flatMap(v => v.vendor || [])
        .sort((a, b) => (a.price || Infinity) - (b.price || Infinity))[0];

    return {
        product_id,
        name: content.title_fa,
        brand: data.brand?.title_fa,
        price: bestOffer ? priceBlock(bestOffer.special_price || bestOffer.price) : null,
        available: !!bestOffer,
        attributes: (data.attributes || []).map(a => ({ title: a.title, value: a.value })),
        images: (data.images || []).map(i => i.src)
    };
};

// --- 3. API Transport Layer ---
async function fetchSearch(query, limit = 10) {
    const resp = await fetch(`${API_BASE}/search/v1${GEO}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit, render: 4 }),
    });
    return resp.json();
}

async function fetchProduct(product_id) {
    const resp = await fetch(`${API_BASE}/products/v2/${product_id}${GEO}`);
    return resp.json();
}

// --- 4. MCP Tool Definitions ---
const TOOLS = [
    {
        name: "search_products",
        description: "Search for products on SnappShop",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string" },
                limit: { type: "number", default: 10 },
            },
            required: ["query"],
        },
    },
    {
        name: "get_product",
        description: "Get detailed information about a specific product",
        inputSchema: {
            type: "object",
            properties: { product_id: { type: "string" } },
            required: ["product_id"],
        },
    }
];

// --- 5. ArvanCloud Edge Handler ---
async function handleRequest(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/tools") {
        return new Response(JSON.stringify({ tools: TOOLS }), {
            headers: { "Content-Type": "application/json" },
        });
    }

    if (path === "/call") {
        try {
            const { name, arguments: args } = await request.json();
            let result;

            if (name === "search_products") {
                const json = await fetchSearch(args.query, args.limit);
                result = normalizeSearch(json, args);
            } else if (name === "get_product") {
                const json = await fetchProduct(args.product_id);
                result = normalizeProduct(json, args);
            } else {
                throw new Error(`Tool ${name} not found`);
            }

            return new Response(JSON.stringify({
                content: [{ type: "text", text: JSON.stringify(result, null, 2) }]
            }), { headers: { "Content-Type": "application/json" } });

        } catch (e) {
            return new Response(JSON.stringify({
                isError: true,
                content: [{ type: "text", text: e.message }]
            }), { status: 500, headers: { "Content-Type": "application/json" } });
        }
    }
    return new Response("ArvanCloud Unified MCP Server", { status: 200 });
}

addEventListener("fetch", (event) => {
    event.respondWith(handleRequest(event.request));
});
