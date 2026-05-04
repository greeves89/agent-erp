#!/usr/bin/env node
/**
 * MCP Postgres ERP Server - Direct database access for ERP tables.
 *
 * Provides agents with read/write access to the ERP database tables
 * (erp_customers, erp_suppliers, erp_articles, erp_orders, erp_invoices, etc.).
 *
 * Environment:
 *   DATABASE_URL - PostgreSQL connection string
 *                  (default: postgresql://agent_erp:devpassword@agent-erp-postgres:5432/agent_erp)
 *   AGENT_ID    - ID of the agent using this server
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import pg from "pg";

const { Pool } = pg;

const DATABASE_URL =
  process.env.DATABASE_URL ||
  "postgresql://agent_erp:devpassword@agent-erp-postgres:5432/agent_erp";
const AGENT_ID = process.env.AGENT_ID || "unknown";

// ── Database connection pool ───────────────────────────────────────────────
const pool = new Pool({
  connectionString: DATABASE_URL,
  max: 5,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000,
});

pool.on("error", (err) => {
  console.error("[postgres-erp] Unexpected pool error:", err.message);
});

async function query(text, params) {
  const client = await pool.connect();
  try {
    const result = await client.query(text, params);
    return result;
  } finally {
    client.release();
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

/** Whitelist: only allow SELECT on erp_* tables. */
function validateReadOnlyQuery(sql) {
  const trimmed = sql.trim().replace(/;+$/, "").trim();
  // Must start with SELECT (case-insensitive)
  if (!/^SELECT\b/i.test(trimmed)) {
    throw new Error("Only SELECT queries are allowed.");
  }
  // Block write statements hidden in CTEs or subqueries
  const forbidden =
    /\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY)\b/i;
  if (forbidden.test(trimmed)) {
    throw new Error(
      "Query contains forbidden statements. Only pure SELECT queries are allowed."
    );
  }
  // All referenced tables must start with erp_ (basic check on FROM / JOIN clauses)
  // We extract table names after FROM and JOIN keywords
  const tableRefPattern =
    /\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)/gi;
  let match;
  while ((match = tableRefPattern.exec(trimmed)) !== null) {
    const tableName = match[1].toLowerCase();
    // Allow information_schema and pg_catalog for metadata queries
    if (
      tableName !== "information_schema" &&
      !tableName.startsWith("pg_") &&
      !tableName.startsWith("erp_")
    ) {
      throw new Error(
        `Access denied: table "${match[1]}" is not an ERP table. Only erp_* tables are allowed.`
      );
    }
  }
}

/** Generate next sequential number (e.g. KD-00001 for customers). */
async function generateNumber(prefix, table, column) {
  const result = await query(
    `SELECT ${column} FROM ${table} WHERE ${column} LIKE $1 ORDER BY ${column} DESC LIMIT 1`,
    [`${prefix}-%`]
  );
  if (result.rows.length === 0) {
    return `${prefix}-00001`;
  }
  const last = result.rows[0][column];
  const num = parseInt(last.split("-")[1], 10) + 1;
  return `${prefix}-${String(num).padStart(5, "0")}`;
}

/** Write an audit log entry. */
async function writeAuditLog(tableName, recordId, action, oldValues, newValues) {
  const changedFields = {};
  if (oldValues && newValues) {
    for (const key of Object.keys(newValues)) {
      if (JSON.stringify(oldValues[key]) !== JSON.stringify(newValues[key])) {
        changedFields[key] = { old: oldValues[key], new: newValues[key] };
      }
    }
  }
  await query(
    `INSERT INTO erp_audit_log (id, table_name, record_id, action, old_values, new_values, changed_fields, performed_by, performed_at)
     VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, NOW())`,
    [
      tableName,
      recordId,
      action,
      oldValues ? JSON.stringify(oldValues) : null,
      newValues ? JSON.stringify(newValues) : null,
      Object.keys(changedFields).length > 0 ? JSON.stringify(changedFields) : null,
      `agent:${AGENT_ID}`,
    ]
  );
}

// ── Valid state transitions for orders ─────────────────────────────────────
const ORDER_TRANSITIONS = {
  draft: ["confirmed", "cancelled"],
  confirmed: ["shipped", "cancelled"],
  shipped: ["delivered", "cancelled"],
  delivered: [],
  cancelled: [],
};

// ── MCP Server Setup ──────────────────────────────────────────────────────

const server = new Server(
  { name: "mcp-postgres-erp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// ── Tool Definitions ──────────────────────────────────────────────────────

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "erp_query",
      description:
        "Run a read-only SQL SELECT query against ERP tables. " +
        "Only SELECT statements on tables starting with 'erp_' are allowed. " +
        "Returns results as a JSON array. Use this for custom reports, lookups, " +
        "and data analysis. Maximum 500 rows returned.",
      inputSchema: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description:
              "SQL SELECT query. Only erp_* tables are accessible. " +
              "Example: SELECT * FROM erp_customers WHERE is_active = true LIMIT 10",
          },
        },
        required: ["query"],
      },
    },
    {
      name: "erp_list_tables",
      description:
        "List all ERP tables with their column names, types, and constraints. " +
        "Use this to discover the database schema before writing queries.",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
    {
      name: "erp_create_customer",
      description:
        "Create a new customer in the ERP system. Auto-generates a customer number " +
        "(KD-XXXXX). Writes an audit log entry.",
      inputSchema: {
        type: "object",
        properties: {
          company_name: {
            type: "string",
            description: "Company name (required).",
          },
          contact_person: {
            type: "string",
            description: "Name of the primary contact person.",
          },
          email: {
            type: "string",
            description: "Email address.",
          },
          phone: {
            type: "string",
            description: "Phone number.",
          },
          address_street: {
            type: "string",
            description: "Street address.",
          },
          address_city: {
            type: "string",
            description: "City.",
          },
          address_zip: {
            type: "string",
            description: "ZIP / postal code.",
          },
          address_country: {
            type: "string",
            description: "Country (default: Deutschland).",
          },
          tax_id: {
            type: "string",
            description: "Tax ID / VAT number.",
          },
          payment_terms_days: {
            type: "number",
            description: "Payment terms in days (default: 30).",
          },
          notes: {
            type: "string",
            description: "Internal notes.",
          },
        },
        required: ["company_name"],
      },
    },
    {
      name: "erp_create_order",
      description:
        "Create a new order (purchase or sales) with line items. " +
        "Auto-generates order number, calculates totals from article prices. " +
        "For sales orders, provide customer_id. For purchase orders, provide supplier_id.",
      inputSchema: {
        type: "object",
        properties: {
          order_type: {
            type: "string",
            enum: ["purchase", "sales"],
            description: "Type of order: 'purchase' (from supplier) or 'sales' (to customer).",
          },
          customer_id: {
            type: "string",
            description: "Customer UUID (required for sales orders).",
          },
          supplier_id: {
            type: "string",
            description: "Supplier UUID (required for purchase orders).",
          },
          items: {
            type: "array",
            items: {
              type: "object",
              properties: {
                article_id: {
                  type: "string",
                  description: "Article UUID.",
                },
                quantity: {
                  type: "number",
                  description: "Quantity to order.",
                },
              },
              required: ["article_id", "quantity"],
            },
            description: "Array of order items with article_id and quantity.",
          },
          delivery_date: {
            type: "string",
            description: "Expected delivery date (YYYY-MM-DD).",
          },
          notes: {
            type: "string",
            description: "Order notes.",
          },
        },
        required: ["order_type", "items"],
      },
    },
    {
      name: "erp_create_invoice",
      description:
        "Create an invoice from an existing order. Copies order items, " +
        "calculates totals, and sets the due date based on customer/supplier payment terms. " +
        "Sales orders create outgoing invoices, purchase orders create incoming invoices.",
      inputSchema: {
        type: "object",
        properties: {
          order_id: {
            type: "string",
            description: "UUID of the order to create an invoice from.",
          },
        },
        required: ["order_id"],
      },
    },
    {
      name: "erp_update_order_status",
      description:
        "Update the status of an order. Validates state transitions: " +
        "draft -> confirmed -> shipped -> delivered. " +
        "Any non-terminal state can transition to cancelled. " +
        "Writes an audit log entry.",
      inputSchema: {
        type: "object",
        properties: {
          order_id: {
            type: "string",
            description: "UUID of the order to update.",
          },
          new_status: {
            type: "string",
            enum: ["draft", "confirmed", "shipped", "delivered", "cancelled"],
            description: "New status for the order.",
          },
        },
        required: ["order_id", "new_status"],
      },
    },
    {
      name: "erp_dashboard",
      description:
        "Get ERP dashboard statistics: customer/supplier/article counts, " +
        "open orders, revenue totals, overdue invoices, and recent activity.",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
  ],
}));

// ── Tool Handlers ─────────────────────────────────────────────────────────

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      // ── erp_query ─────────────────────────────────────────────────────
      case "erp_query": {
        validateReadOnlyQuery(args.query);
        // Add LIMIT if not present to prevent huge result sets
        const trimmed = args.query.trim().replace(/;+$/, "");
        const hasLimit = /\bLIMIT\b/i.test(trimmed);
        const safeSql = hasLimit ? trimmed : `${trimmed} LIMIT 500`;
        const result = await query(safeSql);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  rows: result.rows,
                  rowCount: result.rowCount,
                  fields: result.fields.map((f) => f.name),
                },
                null,
                2
              ),
            },
          ],
        };
      }

      // ── erp_list_tables ───────────────────────────────────────────────
      case "erp_list_tables": {
        const result = await query(`
          SELECT
            t.table_name,
            json_agg(
              json_build_object(
                'column', c.column_name,
                'type', c.data_type,
                'nullable', c.is_nullable,
                'default', c.column_default,
                'max_length', c.character_maximum_length
              ) ORDER BY c.ordinal_position
            ) AS columns
          FROM information_schema.tables t
          JOIN information_schema.columns c
            ON c.table_name = t.table_name AND c.table_schema = t.table_schema
          WHERE t.table_schema = 'public'
            AND t.table_name LIKE 'erp_%'
          GROUP BY t.table_name
          ORDER BY t.table_name
        `);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result.rows, null, 2),
            },
          ],
        };
      }

      // ── erp_create_customer ───────────────────────────────────────────
      case "erp_create_customer": {
        const customerNumber = await generateNumber(
          "KD",
          "erp_customers",
          "customer_number"
        );
        const result = await query(
          `INSERT INTO erp_customers
            (id, customer_number, company_name, contact_person, email, phone,
             address_street, address_city, address_zip, address_country,
             tax_id, payment_terms_days, notes, created_at, updated_at)
           VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW())
           RETURNING id, customer_number, company_name`,
          [
            customerNumber,
            args.company_name,
            args.contact_person || null,
            args.email || null,
            args.phone || null,
            args.address_street || null,
            args.address_city || null,
            args.address_zip || null,
            args.address_country || "Deutschland",
            args.tax_id || null,
            args.payment_terms_days || 30,
            args.notes || null,
          ]
        );

        const customer = result.rows[0];
        await writeAuditLog("erp_customers", customer.id, "INSERT", null, {
          customer_number: customer.customer_number,
          company_name: customer.company_name,
          ...args,
        });

        return {
          content: [
            {
              type: "text",
              text: `Customer created: ${customer.company_name} (${customer.customer_number}, id: ${customer.id})`,
            },
          ],
        };
      }

      // ── erp_create_order ──────────────────────────────────────────────
      case "erp_create_order": {
        const { order_type, customer_id, supplier_id, items, delivery_date, notes } = args;

        if (order_type === "sales" && !customer_id) {
          throw new Error("customer_id is required for sales orders.");
        }
        if (order_type === "purchase" && !supplier_id) {
          throw new Error("supplier_id is required for purchase orders.");
        }
        if (!items || items.length === 0) {
          throw new Error("At least one item is required.");
        }

        // Validate customer/supplier exists
        if (customer_id) {
          const custCheck = await query(
            "SELECT id FROM erp_customers WHERE id = $1",
            [customer_id]
          );
          if (custCheck.rows.length === 0) {
            throw new Error(`Customer ${customer_id} not found.`);
          }
        }
        if (supplier_id) {
          const supCheck = await query(
            "SELECT id FROM erp_suppliers WHERE id = $1",
            [supplier_id]
          );
          if (supCheck.rows.length === 0) {
            throw new Error(`Supplier ${supplier_id} not found.`);
          }
        }

        // Fetch article prices
        const articleIds = items.map((i) => i.article_id);
        const articles = await query(
          `SELECT id, article_number, name, purchase_price, selling_price, tax_rate
           FROM erp_articles WHERE id = ANY($1)`,
          [articleIds]
        );
        const articleMap = new Map(articles.rows.map((a) => [a.id, a]));

        // Verify all articles exist
        for (const item of items) {
          if (!articleMap.has(item.article_id)) {
            throw new Error(`Article ${item.article_id} not found.`);
          }
        }

        // Generate order number
        const prefix = order_type === "sales" ? "SO" : "PO";
        const orderNumber = await generateNumber(
          prefix,
          "erp_orders",
          "order_number"
        );

        // Calculate totals
        let subtotal = 0;
        let taxAmount = 0;
        const orderItems = items.map((item, idx) => {
          const article = articleMap.get(item.article_id);
          const unitPrice =
            order_type === "sales"
              ? parseFloat(article.selling_price || article.purchase_price || 0)
              : parseFloat(article.purchase_price || 0);
          const taxRate = parseFloat(article.tax_rate || 19);
          const lineTotal = unitPrice * item.quantity;
          const lineTax = lineTotal * (taxRate / 100);
          subtotal += lineTotal;
          taxAmount += lineTax;
          return {
            article_id: item.article_id,
            quantity: item.quantity,
            unit_price: unitPrice,
            tax_rate: taxRate,
            line_total: lineTotal,
            position: idx + 1,
          };
        });
        const total = subtotal + taxAmount;

        // Insert order
        const orderResult = await query(
          `INSERT INTO erp_orders
            (id, order_number, order_type, status, customer_id, supplier_id,
             order_date, delivery_date, subtotal, tax_amount, total, notes,
             created_at, updated_at)
           VALUES (gen_random_uuid(), $1, $2, 'draft', $3, $4,
                   CURRENT_DATE, $5, $6, $7, $8, $9, NOW(), NOW())
           RETURNING id, order_number`,
          [
            orderNumber,
            order_type,
            customer_id || null,
            supplier_id || null,
            delivery_date || null,
            subtotal.toFixed(2),
            taxAmount.toFixed(2),
            total.toFixed(2),
            notes || null,
          ]
        );

        const order = orderResult.rows[0];

        // Insert order items
        for (const item of orderItems) {
          await query(
            `INSERT INTO erp_order_items
              (id, order_id, article_id, quantity, unit_price, tax_rate, line_total, position)
             VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7)`,
            [
              order.id,
              item.article_id,
              item.quantity,
              item.unit_price,
              item.tax_rate,
              item.line_total,
              item.position,
            ]
          );
        }

        // Audit log
        await writeAuditLog("erp_orders", order.id, "INSERT", null, {
          order_number: order.order_number,
          order_type,
          items: orderItems.length,
          subtotal,
          tax_amount: taxAmount,
          total,
        });

        return {
          content: [
            {
              type: "text",
              text:
                `Order created: ${order.order_number} (${order_type}, id: ${order.id})\n` +
                `Items: ${orderItems.length}, Subtotal: ${subtotal.toFixed(2)}, ` +
                `Tax: ${taxAmount.toFixed(2)}, Total: ${total.toFixed(2)}`,
            },
          ],
        };
      }

      // ── erp_create_invoice ────────────────────────────────────────────
      case "erp_create_invoice": {
        const { order_id } = args;

        // Fetch order with items
        const orderResult = await query(
          `SELECT o.*, json_agg(
             json_build_object(
               'article_id', oi.article_id,
               'quantity', oi.quantity,
               'unit_price', oi.unit_price,
               'tax_rate', oi.tax_rate,
               'line_total', oi.line_total,
               'position', oi.position
             ) ORDER BY oi.position
           ) AS items
           FROM erp_orders o
           LEFT JOIN erp_order_items oi ON oi.order_id = o.id
           WHERE o.id = $1
           GROUP BY o.id`,
          [order_id]
        );

        if (orderResult.rows.length === 0) {
          throw new Error(`Order ${order_id} not found.`);
        }

        const order = orderResult.rows[0];

        // Determine invoice type from order type
        const invoiceType =
          order.order_type === "sales" ? "outgoing" : "incoming";

        // Calculate due date from payment terms
        let paymentTermsDays = 30;
        if (order.customer_id) {
          const custResult = await query(
            "SELECT payment_terms_days FROM erp_customers WHERE id = $1",
            [order.customer_id]
          );
          if (custResult.rows.length > 0 && custResult.rows[0].payment_terms_days) {
            paymentTermsDays = custResult.rows[0].payment_terms_days;
          }
        } else if (order.supplier_id) {
          const supResult = await query(
            "SELECT payment_terms_days FROM erp_suppliers WHERE id = $1",
            [order.supplier_id]
          );
          if (supResult.rows.length > 0 && supResult.rows[0].payment_terms_days) {
            paymentTermsDays = supResult.rows[0].payment_terms_days;
          }
        }

        // Generate invoice number
        const prefix = invoiceType === "outgoing" ? "RE" : "ER";
        const invoiceNumber = await generateNumber(
          prefix,
          "erp_invoices",
          "invoice_number"
        );

        // Insert invoice
        const invoiceResult = await query(
          `INSERT INTO erp_invoices
            (id, invoice_number, invoice_type, status, order_id, customer_id, supplier_id,
             invoice_date, due_date, subtotal, tax_amount, total, notes,
             created_at, updated_at)
           VALUES (gen_random_uuid(), $1, $2, 'draft', $3, $4, $5,
                   CURRENT_DATE, CURRENT_DATE + $6 * INTERVAL '1 day',
                   $7, $8, $9, $10, NOW(), NOW())
           RETURNING id, invoice_number, due_date`,
          [
            invoiceNumber,
            invoiceType,
            order_id,
            order.customer_id || null,
            order.supplier_id || null,
            paymentTermsDays,
            order.subtotal,
            order.tax_amount,
            order.total,
            `Invoice for order ${order.order_number}`,
          ]
        );

        const invoice = invoiceResult.rows[0];

        // Copy order items to invoice items
        const orderItems = order.items || [];
        for (const item of orderItems) {
          if (!item.article_id) continue; // skip null items from LEFT JOIN
          // Fetch article name for description
          const artResult = await query(
            "SELECT name FROM erp_articles WHERE id = $1",
            [item.article_id]
          );
          const artName =
            artResult.rows.length > 0 ? artResult.rows[0].name : "Unknown";

          await query(
            `INSERT INTO erp_invoice_items
              (id, invoice_id, article_id, description, quantity, unit_price, tax_rate, line_total, position)
             VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8)`,
            [
              invoice.id,
              item.article_id,
              artName,
              item.quantity,
              item.unit_price,
              item.tax_rate,
              item.line_total,
              item.position,
            ]
          );
        }

        // Audit log
        await writeAuditLog("erp_invoices", invoice.id, "INSERT", null, {
          invoice_number: invoice.invoice_number,
          invoice_type: invoiceType,
          order_id,
          order_number: order.order_number,
          total: parseFloat(order.total),
        });

        return {
          content: [
            {
              type: "text",
              text:
                `Invoice created: ${invoice.invoice_number} (${invoiceType}, id: ${invoice.id})\n` +
                `From order: ${order.order_number}\n` +
                `Total: ${parseFloat(order.total).toFixed(2)}, Due: ${invoice.due_date}`,
            },
          ],
        };
      }

      // ── erp_update_order_status ───────────────────────────────────────
      case "erp_update_order_status": {
        const { order_id: oid, new_status } = args;

        // Fetch current order
        const orderResult = await query(
          "SELECT id, order_number, status FROM erp_orders WHERE id = $1",
          [oid]
        );
        if (orderResult.rows.length === 0) {
          throw new Error(`Order ${oid} not found.`);
        }

        const order = orderResult.rows[0];
        const currentStatus = order.status;

        // Validate transition
        const allowed = ORDER_TRANSITIONS[currentStatus];
        if (!allowed) {
          throw new Error(
            `Order ${order.order_number} has unknown status "${currentStatus}".`
          );
        }
        if (!allowed.includes(new_status)) {
          throw new Error(
            `Invalid transition: ${currentStatus} -> ${new_status}. ` +
              `Allowed transitions from "${currentStatus}": [${allowed.join(", ")}].`
          );
        }

        // Update
        await query(
          "UPDATE erp_orders SET status = $1, updated_at = NOW() WHERE id = $2",
          [new_status, oid]
        );

        // Audit log
        await writeAuditLog(
          "erp_orders",
          oid,
          "UPDATE",
          { status: currentStatus },
          { status: new_status }
        );

        return {
          content: [
            {
              type: "text",
              text: `Order ${order.order_number} status updated: ${currentStatus} -> ${new_status}`,
            },
          ],
        };
      }

      // ── erp_dashboard ─────────────────────────────────────────────────
      case "erp_dashboard": {
        const [
          customers,
          suppliers,
          articles,
          orders,
          invoices,
          recentOrders,
          overdueInvoices,
          lowStock,
        ] = await Promise.all([
          query(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_active) AS active FROM erp_customers"
          ),
          query(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_active) AS active FROM erp_suppliers"
          ),
          query(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_active) AS active FROM erp_articles"
          ),
          query(`
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE status = 'draft') AS draft,
              COUNT(*) FILTER (WHERE status = 'confirmed') AS confirmed,
              COUNT(*) FILTER (WHERE status = 'shipped') AS shipped,
              COUNT(*) FILTER (WHERE status = 'delivered') AS delivered,
              COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
              COALESCE(SUM(total) FILTER (WHERE order_type = 'sales' AND status != 'cancelled'), 0) AS sales_total,
              COALESCE(SUM(total) FILTER (WHERE order_type = 'purchase' AND status != 'cancelled'), 0) AS purchase_total
            FROM erp_orders
          `),
          query(`
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE status = 'draft') AS draft,
              COUNT(*) FILTER (WHERE status = 'sent') AS sent,
              COUNT(*) FILTER (WHERE status = 'paid') AS paid,
              COUNT(*) FILTER (WHERE status = 'overdue') AS overdue,
              COALESCE(SUM(total) FILTER (WHERE invoice_type = 'outgoing' AND status != 'cancelled'), 0) AS outgoing_total,
              COALESCE(SUM(total) FILTER (WHERE invoice_type = 'incoming' AND status != 'cancelled'), 0) AS incoming_total,
              COALESCE(SUM(paid_amount), 0) AS total_paid
            FROM erp_invoices
          `),
          query(`
            SELECT order_number, order_type, status, total, created_at
            FROM erp_orders
            ORDER BY created_at DESC
            LIMIT 5
          `),
          query(`
            SELECT invoice_number, invoice_type, total, due_date, customer_id, supplier_id
            FROM erp_invoices
            WHERE status IN ('sent', 'overdue') AND due_date < CURRENT_DATE
            ORDER BY due_date ASC
            LIMIT 10
          `),
          query(`
            SELECT article_number, name, stock_quantity, min_stock_quantity
            FROM erp_articles
            WHERE is_active = true AND stock_quantity <= min_stock_quantity
            ORDER BY stock_quantity ASC
            LIMIT 10
          `),
        ]);

        const dashboard = {
          customers: customers.rows[0],
          suppliers: suppliers.rows[0],
          articles: articles.rows[0],
          orders: orders.rows[0],
          invoices: invoices.rows[0],
          recent_orders: recentOrders.rows,
          overdue_invoices: overdueInvoices.rows,
          low_stock_articles: lowStock.rows,
        };

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(dashboard, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (err) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${err.message}`,
        },
      ],
      isError: true,
    };
  }
});

// ── Cleanup on exit ──────────────────────────────────────────────────────
process.on("SIGINT", async () => {
  await pool.end();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await pool.end();
  process.exit(0);
});

// ── Start ────────────────────────────────────────────────────────────────
const transport = new StdioServerTransport();
await server.connect(transport);
