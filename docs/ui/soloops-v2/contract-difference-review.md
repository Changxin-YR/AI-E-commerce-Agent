# 附件契约差异逐项核对

附件脚本输出 5 个候选旧项与 5 个候选新项；以下逐项一一对应。它们均由新增纯布局容器后的缩进产生。

核对结论：控件文本、事件、路径、query 字段、对象展开参数均相同。TypeScript 扫描器去掉空白后的 token 种类与原文字面值完全一致。源组件业务脚本 SHA-256 全部相同。

## 1. 打开 AI 经营问数，确认范围与模型预算

组件：`src\views\AnalyticsView.vue`。类型：`routerlink`。

旧深链：
```ts
{
        path: '/agent',
        query: {
          shop: shopId,
          mode: 'question',
          ...scopeQuery(scope),
          ...returnTaskQuery(route.query, shopId),
        },
      }
```

新深链：
```ts
{
          path: '/agent',
          query: {
            shop: shopId,
            mode: 'question',
            ...scopeQuery(scope),
            ...returnTaskQuery(route.query, shopId),
          },
        }
```

逐项人工复核（Codex）：仅缩进变化；已映射，不存在新增/消失/重命名行为。

## 2. 前往账单费用核对

组件：`src\views\ImportsView.vue`。类型：`routerlink`。

旧深链：
```ts
{
          path: '/statements',
          query: {
            shop: shopId,
            identity: batch?.data_identity ?? identity,
            channel: batch?.source_channel ?? channel,
          },
        }
```

新深链：
```ts
{
            path: '/statements',
            query: {
              shop: shopId,
              identity: batch?.data_identity ?? identity,
              channel: batch?.source_channel ?? channel,
            },
          }
```

逐项人工复核（Codex）：仅缩进变化；已映射，不存在新增/消失/重命名行为。

## 3. 导入库存快照

组件：`src\views\InventoryView.vue`。类型：`routerlink`。

旧深链：
```ts
{
        path: '/imports',
        query: {
          shop: shopId,
          kind: 'inventory',
          ...scopeQuery(scope),
          ...returnTaskQuery(route.query),
        },
      }
```

新深链：
```ts
{
          path: '/imports',
          query: {
            shop: shopId,
            kind: 'inventory',
            ...scopeQuery(scope),
            ...returnTaskQuery(route.query),
          },
        }
```

逐项人工复核（Codex）：仅缩进变化；已映射，不存在新增/消失/重命名行为。

## 4. 生成 AI Listing 候选

组件：`src\views\ListingsView.vue`。类型：`routerlink`。

旧深链：
```ts
{
        path: '/agent',
        query: {
          shop: shopId,
          mode: 'listing_model',
          product: workspace.product.product_id,
          identity: workspace.product.source.data_identity,
          channel: route.query.channel,
          ...returnTaskQuery(route.query, shopId),
        },
      }
```

新深链：
```ts
{
          path: '/agent',
          query: {
            shop: shopId,
            mode: 'listing_model',
            product: workspace.product.product_id,
            identity: workspace.product.source.data_identity,
            channel: route.query.channel,
            ...returnTaskQuery(route.query, shopId),
          },
        }
```

逐项人工复核（Codex）：仅缩进变化；已映射，不存在新增/消失/重命名行为。

## 5. 生成 AI 客服候选

组件：`src\views\SupportView.vue`。类型：`routerlink`。

旧深链：
```ts
{
            path: '/agent',
            query: {
              shop: shopId,
              mode: 'support_model',
              message: workspace.message.id,
              identity: workspace.message.source.data_identity,
              channel: workspace.message.channel,
              ...returnTaskQuery(route.query, shopId),
            },
          }
```

新深链：
```ts
{
              path: '/agent',
              query: {
                shop: shopId,
                mode: 'support_model',
                message: workspace.message.id,
                identity: workspace.message.source.data_identity,
                channel: workspace.message.channel,
                ...returnTaskQuery(route.query, shopId),
              },
            }
```

逐项人工复核（Codex）：仅缩进变化；已映射，不存在新增/消失/重命名行为。
