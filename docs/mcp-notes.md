# MCP «Сільпо» — нотатки (Фаза 0, розвідка)

Дата: 2026-08-05. Сервер: `https://mcp.silpo.ua/mcp` (streamable HTTP, JSON-RPC 2.0).
ServerInfo: `silpo-mcp-service` v1.104.2, protocolVersion `2025-06-18`.

## Висновки щодо передумов плану

### 0.1 — категорія оптових позицій «Сільпо Хоум» → **частково підтверджено**
- Окремої категорії/тега з назвою «Сільпо Хоум» у дереві категорій НЕМАЄ (переглянуто повне
  дерево `silpo_get_categories_tree`, 28 top-level категорій).
- АЛЕ є прямий механізм оптових/пачкових цін:
  - промоакція **`melkoopt`** = «Гуртом дешевше» (387 товарів, https://silpo.ua/offers/melkoopt);
  - кожен товар акції має поле **`specialPrices: [{price, count, type: "from"}]`** —
    знижка «від N штук»: `count` = мінімальна кількість для оптової ціни, `price` = ціна за штуку.
  - `price` у товарі — роздрібна ціна за штуку; `specialPrices[].price` — оптова ціна за штуку.
- Рішення для сканера: джерело супер-акцій = `silpo_get_products(promotionCode="melkoopt")`,
  `wholesale_pack_size = specialPrices[].count`, `unit_price_wholesale = specialPrices[].price`.
  Поріг знижки рахувати як `(price - specialPrice) / price`.

### 0.2 — URL зображення в MCP-відповіді → **підтверджено** (Варіант A життєздатний)
- Список товарів (`silpo_get_products`, `silpo_find_products_batch`): поле **`image`**
  (напр. `https://images.silpo.ua/v2/products/500x500/webp/<uuid>.png`).
- Деталі товару (`silpo_get_product_details`): поле **`images[]`** (масив URL), а також
  `url` (`https://silpo.ua/product/<slug>` — запасний Варіант B не потрібен, але можливий).
- Отже `bot.send_photo(photo=product.image)` — пріоритетний шлях.

### 0.3 — формат аутентифікації → **підтверджено**
- Bearer access token (OAuth2): заголовок `Authorization: Bearer <token>`.
- Токен читати з `.env` → `MCP_API_KEY`. Термін життя: 30 днів, є `refresh_token`.

## Технічні нотатки про протокол MCP

1. Початкова сесія: `initialize` → заголовок відповіді `Mcp-Session-Id` (передавати далі),
   потім `notifications/initialized`, потім `tools/list`, `tools/call`.
2. Відповіді `tools/call` загортаються в **`result.content[0].text`** як JSON-рядок:
   ```
   {"result": {"content": [{"type": "text", "text": "{\"success\":true,\"products\":[...]}"}]}}
   ```
3. Усі каталогові виклики потребують контекст: `branchId` + `deliveryType` +
   `timeslotStart`/`timeslotEnd`. Розв'язка: `silpo_find_address` → `silpo_get_available_delivery_types`
   → `silpo_get_time_slots`. Робочі слоти дивитись із `start` (сьогоднішні можуть бути закриті).
4. Доступні delivery-типи: `DeliveryHome` (branchId повертається), `WideAssortDelivery` (широкий
   асортимент), `SelfPickup`, `NovaPoshta`, `B2B` тощо.
5. `silpo_get_promotions` повертає коди акцій: `only_online` (1511), **`melkoopt` (387)**,
   `cinotyzhyky` (47), `monstr-rozihrash` (7), `kupuy_ta_zaoshadjuy` (6).
6. Для `silpo_get_products` обов'язковий хоча б один фільтр: `category`, `mustHavePromotion`,
   `promotionCode` або `set`. `promotionCode` автоматично вмикає `mustHavePromotion`.

## Зразок JSON (обрізаний, без чутливих даних)

### tools/call → silpo_get_products(promotionCode="melkoopt") — товар з оптовою ціною
```json
{"result": {"content": [{"type": "text", "text": "{\"success\":true,\"summary\":\"Found 387 products (showing 15)\",\"products\":[{\"id\":\"1ed09877-b528-699c-b5de-c1af87aa927f\",\"name\":\"Снек Oreo молочний\",\"slug\":\"snek-oreo-molochnyi-868167\",\"price\":37.99,\"oldPrice\":null,\"stock\":57,\"available\":true,\"image\":\"https://images.silpo.ua/v2/products/500x500/webp/6baa7f25-0086-4941-b755-ce86f9969bcf.png\",\"weighted\":false,\"step\":1,\"specialPrices\":[{\"price\":18.99,\"count\":3,\"type\":\"from\"}],\"companyId\":\"1ec88c5d-a050-669c-8467-570a157f3e31\",\"branchId\":\"1edb6b38-214b-66d6-a8e0-7f2fdd178564\",\"externalProductId\":868167}]}]}"}}]
```

## Сирі відповіді (лог пробного скрипта)

### initialize

{
  "result": {
    "protocolVersion": "2025-06-18",
    "capabilities": {
      "tools": {
        "listChanged": true
      }
    },
    "serverInfo": {
      "name": "silpo-mcp-service",
      "version": "1.104.2"
    }
  },
  "jsonrpc": "2.0",
  "id": 1
}


### tools/list

{
  "result": {
    "tools": [
      {
        "name": "silpo_find_address",
        "title": "Find Address",
        "description": "Search for address coordinates using text input. Returns latitude and longitude for use with silpo_get_available_delivery_types to find delivery options.\n\nUSE: Pass addresses[].latitude and addresses[].longitude to silpo_get_available_delivery_types.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "address": {
              "type": "string",
              "minLength": 1,
              "description": "Address search text (e.g., \"Київ, вулиця Хрещатик, 1\")"
            }
          },
          "required": [
            "address"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "addresses": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "address": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "city": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "street": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "houseNumber": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "district": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "latitude": {
                    "type": "number"
                  },
                  "longitude": {
                    "type": "number"
                  }
                },
                "required": [
                  "address",
                  "city",
                  "street",
                  "houseNumber",
                  "district",
                  "latitude",
                  "longitude"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "addresses"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_time_slots",
        "title": "Get Delivery Time Slots",
        "description": "Get available delivery time slots for a Silpo branch.\n\nUSAGE: Use slots[].start and slots[].end with silpo_update_shopping_cart timeslot param. Only pick slots where available=true.\n\nTIMES: All times in the response are UTC — always convert to user's local timezone when presenting.\n\nBRANCH: Prefer using branchId from silpo_get_shopping_cart_by_id (existing cart). Only use silpo_get_available_delivery_types if user wants to change address.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id or silpo_get_available_delivery_types"
            },
            "deliveryTypes": {
              "description": "Filter by delivery types",
              "type": "array",
              "items": {
                "type": "string",
                "enum": [
                  "NovaPoshta",
                  "JustInPost",
                  "LongDelivery",
                  "JustIn",
                  "DeliveryExpressFood",
                  "DeliveryExpress",
                  "DeliveryGlovo",
                  "DeliveryOffice",
                  "DeliveryFlat",
                  "DeliveryHome",
                  "SelfPickup",
                  "WideAssortDelivery"
                ]
              }
            },
            "limit": {
              "description": "Max slots to return (default: 25)",
              "type": "integer",
              "minimum": 1,
              "maximum": 100
            },
            "start": {
              "description": "Start date-time in ISO format",
              "type": "string"
            },
            "end": {
              "description": "End date-time in ISO format",
              "type": "string"
            }
          },
          "required": [
            "branchId"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "slots": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "start": {
                    "type": "string"
                  },
                  "end": {
                    "type": "string"
                  },
                  "available": {
                    "type": "boolean"
                  },
                  "deliveryType": {
                    "type": "string"
                  },
                  "deliveryCost": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "deliveryCostMap": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "cost": {
                          "type": "number"
                        },
                        "fromOrderCost": {
                          "type": "number"
                        }
                      },
                      "required": [
                        "cost",
                        "fromOrderCost"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "minOrderCost": {
                    "type": "number"
                  },
                  "maxWeight": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "constraints": {
                    "type": "object",
                    "properties": {
                      "isLimitedAlcohol": {
                        "type": "boolean"
                      },
                      "isLimitedTobacco": {
                        "type": "boolean"
                      },
                      "isLimitedCookedFood": {
                        "type": "boolean"
                      },
                      "isLimitedOwnCooking": {
                        "type": "boolean"
                      }
                    },
                    "required": [
                      "isLimitedAlcohol",
                      "isLimitedTobacco",
                      "isLimitedCookedFood",
                      "isLimitedOwnCooking"
                    ],
                    "additionalProperties": false
                  },
                  "fast": {
                    "anyOf": [
                      {
                        "type": "object",
                        "properties": {
                          "cost": {
                            "type": "number"
                          },
                          "time": {
                            "type": "number"
                          }
                        },
                        "required": [
                          "cost",
                          "time"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "start",
                  "end",
                  "available",
                  "deliveryType",
                  "deliveryCost",
                  "deliveryCostMap",
                  "minOrderCost",
                  "maxWeight",
                  "constraints",
                  "fast"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "slots",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_find_products_batch",
        "title": "Find Products Batch",
        "description": "Search for multiple products at once (semicolon-separated, max 30). Prefer getting branchId/deliveryType/timeslot from silpo_get_shopping_cart_by_id (existing cart).\n\nBUDGET: If user mentions a budget, ALWAYS fill the cart as close to the budget limit as possible. Maximize the total spend without exceeding it — add more items or increase quantities to use the full budget.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id or silpo_get_available_delivery_types"
            },
            "deliveryType": {
              "type": "string",
              "enum": [
                "Unknown",
                "SelfPickup",
                "DeliveryHome",
                "DeliveryFlat",
                "DeliveryOffice",
                "DeliveryGlovo",
                "DeliveryExpress",
                "DeliveryExpressFood",
                "JustIn",
                "LongDelivery",
                "JustInPost",
                "NovaPoshta",
                "DeliveryExpressByPromise",
                "WideAssortDelivery"
              ],
              "description": "Delivery type"
            },
            "timeslotStart": {
              "type": "string",
              "description": "Timeslot start"
            },
            "timeslotEnd": {
              "type": "string",
              "description": "Timeslot end"
            },
            "products": {
              "maxItems": 30,
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "Array of product names to search for (max 30)"
            },
            "limit": {
              "description": "Results per search (default: 30)",
              "type": "integer",
              "minimum": 1,
              "maximum": 100
            }
          },
          "required": [
            "branchId",
            "deliveryType",
            "timeslotStart",
            "timeslotEnd",
            "products"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "queries": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "query": {
                    "type": "string"
                  },
                  "totalFound": {
                    "type": "number"
                  },
                  "products": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "id": {
                          "type": "string"
                        },
                        "name": {
                          "type": "string"
                        },
                        "slug": {
                          "type": "string"
                        },
                        "price": {
                          "type": "number"
                        },
                        "oldPrice": {
                          "anyOf": [
                            {
                              "type": "number"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "stock": {
                          "type": "number"
                        },
                        "available": {
                          "type": "boolean"
                        },
                        "image": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "weighted": {
                          "type": "boolean"
                        },
                        "step": {
                          "type": "number"
                        },
                        "specialPrices": {
                          "anyOf": [
                            {
                              "type": "array",
                              "items": {
                                "type": "object",
                                "properties": {
                                  "price": {
                                    "type": "number"
                                  },
                                  "count": {
                                    "type": "number"
                                  },
                                  "type": {
                                    "type": "string"
                                  }
                                },
                                "required": [
                                  "price",
                                  "count",
                                  "type"
                                ],
                                "additionalProperties": false
                              }
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "companyId": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "branchId": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "externalProductId": {
                          "anyOf": [
                            {
                              "type": "number"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        }
                      },
                      "required": [
                        "id",
                        "name",
                        "slug",
                        "price",
                        "oldPrice",
                        "stock",
                        "available",
                        "image",
                        "weighted",
                        "step",
                        "specialPrices",
                        "companyId",
                        "branchId",
                        "externalProductId"
                      ],
                      "additionalProperties": false
                    }
                  }
                },
                "required": [
                  "query",
                  "totalFound",
                  "products"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "totalQueries": {
                  "type": "number"
                },
                "totalProducts": {
                  "type": "number"
                }
              },
              "required": [
                "totalQueries",
                "totalProducts"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "queries",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_products",
        "title": "Get Products",
        "description": "Browse products at a Silpo branch with filters. At least one filter required: category, mustHavePromotion, promotionCode, or set. Prefer getting branchId/deliveryType/timeslot from silpo_get_shopping_cart_by_id (existing cart). NOTE: promotionCode automatically enables mustHavePromotion.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id or silpo_get_available_delivery_types"
            },
            "deliveryType": {
              "type": "string",
              "enum": [
                "Unknown",
                "SelfPickup",
                "DeliveryHome",
                "DeliveryFlat",
                "DeliveryOffice",
                "DeliveryGlovo",
                "DeliveryExpress",
                "DeliveryExpressFood",
                "JustIn",
                "LongDelivery",
                "JustInPost",
                "NovaPoshta",
                "DeliveryExpressByPromise",
                "WideAssortDelivery"
              ],
              "description": "Delivery type"
            },
            "timeslotStart": {
              "type": "string",
              "description": "Timeslot start"
            },
            "timeslotEnd": {
              "type": "string",
              "description": "Timeslot end"
            },
            "mustHavePromotion": {
              "description": "Only show promotional products",
              "type": "boolean"
            },
            "category": {
              "description": "Category filter",
              "type": "string"
            },
            "promotionCode": {
              "description": "Promotion code from silpo_get_promotions",
              "type": "string"
            },
            "inStock": {
              "description": "Only show in-stock products",
              "type": "boolean"
            },
            "set": {
              "description": "Set slug from silpo_get_product_sets to browse products in that set",
              "type": "string"
            },
            "limit": {
              "description": "Max results (default: 25)",
              "type": "integer",
              "minimum": 1,
              "maximum": 100
            },
            "offset": {
              "description": "Skip items for pagination",
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            "sortBy": {
              "description": "Sort field (default: popularity)",
              "type": "string",
              "enum": [
                "popularity",
                "score",
                "title",
                "price",
                "promotion",
                "productsList",
                "slugsList",
                "guestRating",
                "carouselList"
              ]
            },
            "sortDirection": {
              "description": "Sort direction",
              "type": "string",
              "enum": [
                "asc",
                "desc"
              ]
            },
            "fromPrice": {
              "description": "Min price",
              "type": "number"
            },
            "toPrice": {
              "description": "Max price",
              "type": "number"
            }
          },
          "required": [
            "branchId",
            "deliveryType",
            "timeslotStart",
            "timeslotEnd"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "products": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "name": {
                    "type": "string"
                  },
                  "slug": {
                    "type": "string"
                  },
                  "price": {
                    "type": "number"
                  },
                  "oldPrice": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "stock": {
                    "type": "number"
                  },
                  "available": {
                    "type": "boolean"
                  },
                  "image": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "weighted": {
                    "type": "boolean"
                  },
                  "step": {
                    "type": "number"
                  },
                  "specialPrices": {
                    "anyOf": [
                      {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "properties": {
                            "price": {
                              "type": "number"
                            },
                            "count": {
                              "type": "number"
                            },
                            "type": {
                              "type": "string"
                            }
                          },
                          "required": [
                            "price",
                            "count",
                            "type"
                          ],
                          "additionalProperties": false
                        }
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "companyId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "branchId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "externalProductId": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "name",
                  "slug",
                  "price",
                  "oldPrice",
                  "stock",
                  "available",
                  "image",
                  "weighted",
                  "step",
                  "specialPrices",
                  "companyId",
                  "branchId",
                  "externalProductId"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "limit": {
                  "type": "number"
                },
                "offset": {
                  "type": "number"
                },
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "limit",
                "offset",
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "products",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_promotions",
        "title": "Get Promotions",
        "description": "List active promotions at a Silpo branch. Returns promotion codes for use with silpo_get_products.\n\nAll inputs must be taken from silpo_get_shopping_cart_by_id: branchId, deliveryType, timeslotStart (slot.start), timeslotEnd (slot.end).",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id"
            },
            "deliveryType": {
              "type": "string",
              "enum": [
                "Unknown",
                "SelfPickup",
                "DeliveryHome",
                "DeliveryFlat",
                "DeliveryOffice",
                "DeliveryGlovo",
                "DeliveryExpress",
                "DeliveryExpressFood",
                "JustIn",
                "LongDelivery",
                "JustInPost",
                "NovaPoshta",
                "DeliveryExpressByPromise",
                "WideAssortDelivery"
              ],
              "description": "Delivery type from silpo_get_shopping_cart_by_id"
            },
            "timeslotStart": {
              "type": "string",
              "description": "Timeslot start ISO timestamp from silpo_get_shopping_cart_by_id slot.start"
            },
            "timeslotEnd": {
              "type": "string",
              "description": "Timeslot end ISO timestamp from silpo_get_shopping_cart_by_id slot.end"
            }
          },
          "required": [
            "branchId",
            "deliveryType",
            "timeslotStart",
            "timeslotEnd"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "promotions": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "code": {
                    "type": "string"
                  },
                  "title": {
                    "type": "string"
                  },
                  "productCount": {
                    "type": "number"
                  },
                  "url": {
                    "type": "string"
                  }
                },
                "required": [
                  "code",
                  "title",
                  "productCount",
                  "url"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "promotions"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_popular_categories",
        "title": "Get Popular Categories",
        "description": "List popular/trending categories at a Silpo branch.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id or silpo_get_available_delivery_types"
            },
            "deliveryType": {
              "type": "string",
              "enum": [
                "Unknown",
                "SelfPickup",
                "DeliveryHome",
                "DeliveryFlat",
                "DeliveryOffice",
                "DeliveryGlovo",
                "DeliveryExpress",
                "DeliveryExpressFood",
                "JustIn",
                "LongDelivery",
                "JustInPost",
                "NovaPoshta",
                "DeliveryExpressByPromise",
                "WideAssortDelivery"
              ],
              "description": "Delivery type"
            }
          },
          "required": [
            "branchId",
            "deliveryType"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "categories": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "slug": {
                    "type": "string"
                  },
                  "title": {
                    "type": "string"
                  },
                  "url": {
                    "type": "string"
                  }
                },
                "required": [
                  "id",
                  "slug",
                  "title",
                  "url"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "categories"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_category",
        "title": "Get Category Details",
        "description": "Get detailed info about a specific category (name, path, price range, children).",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id or silpo_get_available_delivery_types"
            },
            "deliveryType": {
              "type": "string",
              "enum": [
                "Unknown",
                "SelfPickup",
                "DeliveryHome",
                "DeliveryFlat",
                "DeliveryOffice",
                "DeliveryGlovo",
                "DeliveryExpress",
                "DeliveryExpressFood",
                "JustIn",
                "LongDelivery",
                "JustInPost",
                "NovaPoshta",
                "DeliveryExpressByPromise",
                "WideAssortDelivery"
              ],
              "description": "Delivery type"
            },
            "categorySlug": {
              "type": "string",
              "description": "Category slug from silpo_get_popular_categories or silpo_get_categories_tree"
            }
          },
          "required": [
            "branchId",
            "deliveryType",
            "categorySlug"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "category": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "string"
                },
                "slug": {
                  "type": "string"
                },
                "title": {
                  "type": "string"
                },
                "url": {
                  "type": "string"
                },
                "path": {
                  "anyOf": [
                    {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "slug": {
                            "type": "string"
                          },
                          "title": {
                            "type": "string"
                          }
                        },
                        "required": [
                          "slug",
                          "title"
                        ],
                        "additionalProperties": false
                      }
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "priceRange": {
                  "anyOf": [
                    {
                      "type": "object",
                      "properties": {
                        "min": {
                          "type": "number"
                        },
                        "max": {
                          "type": "number"
                        }
                      },
                      "required": [
                        "min",
                        "max"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "children": {
                  "anyOf": [
                    {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "id": {
                            "type": "string"
                          },
                          "slug": {
                            "type": "string"
                          },
                          "title": {
                            "type": "string"
                          }
                        },
                        "required": [
                          "id",
                          "slug",
                          "title"
                        ],
                        "additionalProperties": false
                      }
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "id",
                "slug",
                "title",
                "url",
                "path",
                "priceRange",
                "children"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "category"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_categories",
        "title": "Get Categories",
        "description": "List categories at a Silpo branch. Optionally filter by parent category to get subcategories.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id or silpo_get_available_delivery_types"
            },
            "parentId": {
              "description": "Parent category ID to get subcategories",
              "type": "string"
            },
            "limit": {
              "description": "Max categories (default: 1000)",
              "type": "integer",
              "minimum": 1,
              "maximum": 1000
            },
            "offset": {
              "description": "Skip for pagination",
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            }
          },
          "required": [
            "branchId"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "categories": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "slug": {
                    "type": "string"
                  },
                  "title": {
                    "type": "string"
                  },
                  "parentId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "slug",
                  "title",
                  "parentId"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "limit": {
                  "type": "number"
                },
                "offset": {
                  "type": "number"
                },
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "limit",
                "offset",
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "categories",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_categories_tree",
        "title": "Get Categories Tree",
        "description": "Get the full category hierarchy for a Silpo branch and time slot.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id"
            },
            "deliveryType": {
              "type": "string",
              "enum": [
                "Unknown",
                "SelfPickup",
                "DeliveryHome",
                "DeliveryFlat",
                "DeliveryOffice",
                "DeliveryGlovo",
                "DeliveryExpress",
                "DeliveryExpressFood",
                "JustIn",
                "LongDelivery",
                "JustInPost",
                "NovaPoshta",
                "DeliveryExpressByPromise",
                "WideAssortDelivery"
              ],
              "description": "Delivery type from silpo_get_shopping_cart_by_id"
            },
            "timeslotStart": {
              "type": "string",
              "description": "Timeslot start from silpo_get_shopping_cart_by_id"
            },
            "timeslotEnd": {
              "type": "string",
              "description": "Timeslot end from silpo_get_shopping_cart_by_id"
            }
          },
          "required": [
            "branchId",
            "deliveryType",
            "timeslotStart",
            "timeslotEnd"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "tree": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {},
                "additionalProperties": {}
              }
            }
          },
          "required": [
            "success",
            "summary",
            "tree"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_shopping_cart",
        "title": "Get My Shopping Cart",
        "description": "Get the authenticated user's shopping cart ID. START HERE — use this first, then silpo_get_shopping_cart_by_id to get branchId, deliveryType, and timeslot for product searches.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "shoppingCartId": {
              "type": "string"
            }
          },
          "required": [
            "success",
            "shoppingCartId"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_shopping_cart_by_id",
        "title": "Get Shopping Cart Details",
        "description": "View detailed shopping cart contents including products, delivery settings, totals, and errors/warnings.\n\nRESPONSE FIELDS GUIDE:\n- cart.shipments[0].branchId — use as branchId for product searches\n- cart.deliveryType — use as deliveryType for product searches\n- cart.timeslot.start / cart.timeslot.end — use as timeslotStart/timeslotEnd for product searches\n- cart.shipments[].products[].productId + companyId — use for add_or_update_cart_products\n- cart.calculation.validations[] — errors/warnings that block checkout\n- cart.calculation.total — full order total before discounts\n- cart.calculation.totalAfterDiscounts — the actual amount the user will PAY (always show this to the user, not total)\n- cart.calculation.certificatesTotal — total discount applied from gift certificates\n- cart.calculation.delivery.totalWeight — total weight\n\nEXPRESS DELIVERY:\n- If cart.deliveryType = \"DeliveryExpressByPromise\": order will be delivered in ~cart.calculation.delivery.deliveryExpressByPromise.promiseTime seconds (convert to minutes for user). Use \"DeliveryHome\" as deliveryType for all other tools (product searches, time slots, etc.).\n- If cart.deliveryType != \"DeliveryExpressByPromise\": check cart.calculation.delivery.deliveryExpressByPromise. If isAvailable=true AND isTemporarilyUnavailable=false — HIGHLIGHT to user: \"Express delivery available! Delivery in ~{promiseTime/60} minutes for ₴{price}\". If user wants express, update cart deliveryType to \"DeliveryExpressByPromise\" via silpo_update_shopping_cart.\n\nTIMESLOT VALIDATION (MANDATORY — DO THIS IMMEDIATELY):\nYou MUST call silpo_get_time_slots IMMEDIATELY after this tool (branchId=cart.shipments[0].branchId, deliveryTypes=[cart.deliveryType], start=now, limit=10). Then check if cart.timeslot (start + end) exists in the returned slots where available=true. If not found or not available — ask user to pick a new timeslot and update via silpo_update_shopping_cart. Do NOT proceed with any other operations until timeslot is confirmed valid.\n\nVALIDATION HANDLING:\n- ERRORS in cart.calculation.validations[] MUST be highlighted to the user — they block checkout\n- WARNINGS MUST be communicated clearly\n- Timeslot times are UTC — always convert to user's local timezone\n\nPLASTIC BAGS: ALWAYS ignore plastic bags (пакет, пакет з пакетів, пакет-майка) when reordering products from this cart — never add them.\n\nCHECKOUT LINK: If checkoutWebLink/checkoutMobileLink are present in the response, ALWAYS show BOTH links to the user — checkoutWebLink labeled \"Оформити на сайті\" and checkoutMobileLink labeled \"Оформити в застосунку\".\n\nБАЛАБОНУСИ (BONUS PAY):\nCheck cart.calculation.loyalty after this tool:\n- If bonusRequested is null AND bonusAvailable > 0 AND bonusTotal >= bonusAvailable AND isEnabled is true — ALWAYS propose to user: \"У вас є {bonusAvailable} балабонусів. Бажаєте їх застосувати для оплати замовлення?\"\n- If user agrees — call silpo_update_shopping_cart with bonusRequested = bonusAvailable (or user-specified amount ≤ bonusAvailable)\n- If user declines — proceed without bonuses\n- bonusTotal — total balance the user has; bonusAvailable — amount applicable to this cart",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "shoppingCartId": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
              "description": "Cart ID from silpo_get_my_shopping_cart"
            }
          },
          "required": [
            "shoppingCartId"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "cart": {
              "type": "object",
              "properties": {},
              "additionalProperties": {},
              "description": "Full shopping cart object from API"
            },
            "loyalty": {
              "anyOf": [
                {
                  "type": "object",
                  "properties": {
                    "bonusAvailable": {
                      "type": "number"
                    },
                    "bonusTotal": {
                      "type": "number"
                    },
                    "bonusRequested": {
                      "anyOf": [
                        {
                          "type": "number"
                        },
                        {
                          "type": "null"
                        }
                      ]
                    },
                    "isEnabled": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "bonusAvailable",
                    "bonusTotal",
                    "bonusRequested",
                    "isEnabled"
                  ],
                  "additionalProperties": false
                },
                {
                  "type": "null"
                }
              ],
              "description": "Балабонуси loyalty bonus info (null if not available)"
            },
            "checkoutWebLink": {
              "description": "Checkout link for web/desktop (present when cart is non-empty and error-free)",
              "type": "string"
            },
            "checkoutMobileLink": {
              "description": "Checkout link for mobile apps (present when cart is non-empty and error-free)",
              "type": "string"
            }
          },
          "required": [
            "success",
            "cart",
            "loyalty"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_add_or_update_cart_products",
        "title": "Add/Update Cart Products",
        "description": "Add products to shopping cart or update quantities. IMPORTANT: After this action, ALWAYS call silpo_get_shopping_cart_by_id to verify the cart and report any errors/warnings to the user. Requires productId, companyId, and branchId from product search results.\n\nSTOCK LIMIT: NEVER add quantity exceeding the product's stock value. Before calling this tool, always check the stock field and inform the user of the maximum available quantity. If user requests more than stock — warn them and cap at stock value.\n\nBUDGET: If user specified a budget, fill the cart as close to the budget limit as possible. Maximize total spend without exceeding it — suggest additional items or increase quantities to use the full budget.\n\nPLASTIC BAGS: ALWAYS ignore plastic bags (пакет, пакет з пакетів, пакет-майка) — never add them to cart. Skip them silently without asking the user.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "shoppingCartId": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
              "description": "Cart ID from silpo_get_my_shopping_cart"
            },
            "products": {
              "minItems": 1,
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "productId": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    "description": "Product ID from find-products or get-products"
                  },
                  "companyId": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    "description": "Company ID from product search response"
                  },
                  "branchId": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    "description": "Branch ID from product search response"
                  },
                  "quantity": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Quantity to add. For weight goods, use multiples of addToBasketStep from product data (e.g. 0.5 for 500g step)"
                  },
                  "addQuantity": {
                    "description": "Add to existing quantity (true) or replace (false)",
                    "type": "boolean"
                  },
                  "comment": {
                    "description": "Special instructions",
                    "type": "string"
                  }
                },
                "required": [
                  "productId",
                  "companyId",
                  "branchId",
                  "quantity"
                ]
              },
              "description": "Products to add/update"
            }
          },
          "required": [
            "shoppingCartId",
            "products"
          ]
        },
        "annotations": {
          "readOnlyHint": false,
          "destructiveHint": false,
          "idempotentHint": false,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "products": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "productId": {
                    "type": "string"
                  },
                  "quantity": {
                    "type": "number"
                  }
                },
                "required": [
                  "productId",
                  "quantity"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "products"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_remove_cart_products",
        "title": "Remove Cart Products",
        "description": "Remove products from shopping cart. IMPORTANT: After this action, ALWAYS call silpo_get_shopping_cart_by_id to verify the cart and report any errors/warnings to the user. Product IDs from silpo_get_shopping_cart_by_id.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "shoppingCartId": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
              "description": "Cart ID from silpo_get_my_shopping_cart"
            },
            "products": {
              "minItems": 1,
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "productId": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    "description": "Product ID from cart"
                  }
                },
                "required": [
                  "productId"
                ]
              },
              "description": "Products to remove"
            }
          },
          "required": [
            "shoppingCartId",
            "products"
          ]
        },
        "annotations": {
          "readOnlyHint": false,
          "destructiveHint": true,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "products": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "productId": {
                    "type": "string"
                  }
                },
                "required": [
                  "productId"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "products"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_clear_shopping_cart",
        "title": "Clear Shopping Cart",
        "description": "Remove all products from the shopping cart. IMPORTANT: After this action, ALWAYS call silpo_get_shopping_cart_by_id to verify the cart.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "shoppingCartId": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
              "description": "Cart ID from silpo_get_my_shopping_cart"
            }
          },
          "required": [
            "shoppingCartId"
          ]
        },
        "annotations": {
          "readOnlyHint": false,
          "destructiveHint": true,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            }
          },
          "required": [
            "success",
            "summary"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_update_shopping_cart",
        "title": "Update Shopping Cart",
        "description": "Update cart delivery settings. IMPORTANT: After this action, ALWAYS call silpo_get_shopping_cart_by_id to verify the cart and report any errors/warnings to the user.\n\nFor DeliveryExpressByPromise deliveryType: Use this to switch to express delivery. Copy address, shipments, timeslot from the current cart response as-is. Only change deliveryType to \"DeliveryExpressByPromise\". The branchId in shipments will be automatically resolved from deliveryExpressByPromise.branchId.\n\nFor NovaPoshta deliveryType: 1) Get settlement via silpo_find_nova_poshta_settlements 2) Get office via silpo_find_nova_poshta_offices 3) Get branchId via silpo_list_branches(hasNP=true). Build address as: { \"addressType\": \"nova-poshta\", \"city\": settlement.title, \"region\": settlement.area, \"latitude\": String(office.latitude), \"longitude\": String(office.longitude), \"officeId\": office.id, \"street\": \"<type> #<number>\" } where type is \"Відділення\" for office or \"Поштомат\" for parcelLocker. Set shipments with the NP branch companyId + branchId.\n\nFor SelfPickup deliveryType: address MUST use data from silpo_list_branches (hasPickup=true). Build address as: { \"addressType\": \"self-pickup\", \"city\": branch.cityFull, \"locality\": branch.addressFull, \"street\": branch.addressFull, \"latitude\": branch.latitude, \"longitude\": branch.longitude }. Set shipments with the branch companyId + branchId.\n\nFor other delivery types: the address object MUST be passed exactly as received from silpo_get_shopping_cart_by_id (requires addressType, latitude, longitude as strings). Do NOT construct the address manually — always copy it from the cart response. The shipments array must also come from the cart response.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "shoppingCartId": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
              "description": "Cart ID from silpo_get_my_shopping_cart"
            },
            "deliveryType": {
              "type": "string",
              "description": "Delivery type"
            },
            "timeslot": {
              "type": "object",
              "properties": {
                "start": {
                  "type": "string",
                  "description": "Start time ISO format"
                },
                "end": {
                  "type": "string",
                  "description": "End time ISO format"
                }
              },
              "required": [
                "start",
                "end"
              ],
              "description": "Delivery timeslot"
            },
            "address": {
              "type": "object",
              "propertyNames": {
                "type": "string"
              },
              "additionalProperties": {},
              "description": "Full address object from silpo_get_shopping_cart_by_id response (must include addressType, latitude, longitude)"
            },
            "shipments": {
              "minItems": 1,
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "companyId": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    "description": "Company ID from cart shipment"
                  },
                  "branchId": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    "description": "Branch ID from cart shipment"
                  }
                },
                "required": [
                  "companyId",
                  "branchId"
                ]
              },
              "description": "Shipments array from silpo_get_shopping_cart_by_id response (do NOT construct manually)"
            },
            "branchId": {
              "description": "New branch ID (optional)",
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
            },
            "feedbackChanges": {
              "description": "Product change preference",
              "type": "string",
              "enum": [
                "approvedChanges",
                "disapprovedChanges"
              ]
            },
            "feedbackContacts": {
              "description": "Contact preference",
              "type": "string",
              "enum": [
                "call",
                "doNotCall"
              ]
            },
            "isAdultConfirmed": {
              "description": "Confirm adult products",
              "type": "boolean"
            },
            "promoCode": {
              "description": "Promo code to apply",
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ]
            },
            "bonusRequested": {
              "description": "Балабонуси to apply: set to bonusAvailable (or less if user specifies an exact amount) from silpo_get_shopping_cart_by_id to pay with bonuses, or null to remove bonus payment",
              "anyOf": [
                {
                  "type": "number"
                },
                {
                  "type": "null"
                }
              ]
            }
          },
          "required": [
            "shoppingCartId",
            "deliveryType",
            "timeslot",
            "address",
            "shipments"
          ]
        },
        "annotations": {
          "readOnlyHint": false,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "shoppingCartId": {
              "type": "string"
            }
          },
          "required": [
            "success",
            "summary",
            "shoppingCartId"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_online_orders",
        "title": "Get My Online Orders",
        "description": "View online delivery order history with product details. Only shows orders placed via silpo.ua or Silpo mobile apps (not in-store purchases). Product IDs can be used to reorder via silpo_add_or_update_cart_products.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "limit": {
              "description": "Max orders (default: 10)",
              "type": "integer",
              "minimum": 1,
              "maximum": 100
            },
            "offset": {
              "description": "Skip for pagination",
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            }
          }
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "orders": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "orderId": {
                    "type": "string"
                  },
                  "number": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "status": {
                    "type": "string"
                  },
                  "createdAt": {
                    "type": "string"
                  },
                  "amount": {
                    "type": "number"
                  },
                  "discount": {
                    "type": "number"
                  },
                  "delivery": {
                    "anyOf": [
                      {
                        "type": "object",
                        "properties": {
                          "type": {
                            "type": "string"
                          },
                          "timeSlot": {
                            "anyOf": [
                              {
                                "type": "object",
                                "properties": {
                                  "from": {
                                    "type": "string"
                                  },
                                  "to": {
                                    "type": "string"
                                  }
                                },
                                "required": [
                                  "from",
                                  "to"
                                ],
                                "additionalProperties": false
                              },
                              {
                                "type": "null"
                              }
                            ]
                          },
                          "deliveredAt": {
                            "anyOf": [
                              {
                                "type": "string"
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "type",
                          "timeSlot",
                          "deliveredAt"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "address": {
                    "anyOf": [
                      {
                        "type": "object",
                        "properties": {
                          "city": {
                            "anyOf": [
                              {
                                "type": "string"
                              },
                              {
                                "type": "null"
                              }
                            ]
                          },
                          "street": {
                            "anyOf": [
                              {
                                "type": "string"
                              },
                              {
                                "type": "null"
                              }
                            ]
                          },
                          "building": {
                            "anyOf": [
                              {
                                "type": "string"
                              },
                              {
                                "type": "null"
                              }
                            ]
                          },
                          "apartment": {
                            "anyOf": [
                              {
                                "type": "string"
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "city",
                          "street",
                          "building",
                          "apartment"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "products": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "id": {
                          "type": "string"
                        },
                        "name": {
                          "type": "string"
                        },
                        "price": {
                          "type": "number"
                        },
                        "quantity": {
                          "type": "number"
                        },
                        "subtotal": {
                          "type": "number"
                        },
                        "removed": {
                          "type": "boolean"
                        },
                        "image": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "companyId": {
                          "type": "string"
                        },
                        "branchId": {
                          "type": "string"
                        }
                      },
                      "required": [
                        "id",
                        "name",
                        "price",
                        "quantity",
                        "subtotal",
                        "removed",
                        "image",
                        "companyId",
                        "branchId"
                      ],
                      "additionalProperties": false
                    }
                  }
                },
                "required": [
                  "orderId",
                  "number",
                  "status",
                  "createdAt",
                  "amount",
                  "discount",
                  "delivery",
                  "address",
                  "products"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "limit": {
                  "type": "number"
                },
                "offset": {
                  "type": "number"
                },
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "limit",
                "offset",
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "orders",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_product_details",
        "title": "Get Product Details",
        "description": "Get detailed information about a specific product by branch and slug. Returns product attributes, nutrition info, and image URLs.\n\nCRITICAL: The slug parameter MUST come from the slug field in silpo_find_products_batch or silpo_get_products results. NEVER construct or guess a slug from a product name — slugs are generated by Silpo and cannot be derived from names. If you don't have a slug from a previous search, call silpo_find_products_batch first.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id"
            },
            "slug": {
              "type": "string",
              "description": "Product slug — MUST be taken from slug field in silpo_find_products_batch or silpo_get_products results. Never construct from name."
            },
            "deliveryType": {
              "type": "string",
              "description": "Delivery type from silpo_get_shopping_cart_by_id"
            },
            "timeslotStart": {
              "type": "string",
              "description": "Timeslot start from silpo_get_shopping_cart_by_id"
            },
            "timeslotEnd": {
              "type": "string",
              "description": "Timeslot end from silpo_get_shopping_cart_by_id"
            }
          },
          "required": [
            "branchId",
            "slug",
            "deliveryType",
            "timeslotStart",
            "timeslotEnd"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "product": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "string"
                },
                "name": {
                  "type": "string"
                },
                "slug": {
                  "type": "string"
                },
                "price": {
                  "type": "number"
                },
                "oldPrice": {
                  "anyOf": [
                    {
                      "type": "number"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "stock": {
                  "type": "number"
                },
                "available": {
                  "type": "boolean"
                },
                "weighted": {
                  "type": "boolean"
                },
                "step": {
                  "type": "number"
                },
                "ratio": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "url": {
                  "type": "string"
                },
                "images": {
                  "type": "array",
                  "items": {
                    "type": "string"
                  }
                },
                "attributes": {
                  "anyOf": [
                    {
                      "type": "object",
                      "propertyNames": {
                        "type": "string"
                      },
                      "additionalProperties": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "number"
                          }
                        ]
                      }
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "companyId": {
                  "type": "string"
                },
                "branchId": {
                  "type": "string"
                }
              },
              "required": [
                "id",
                "name",
                "slug",
                "price",
                "oldPrice",
                "stock",
                "available",
                "weighted",
                "step",
                "ratio",
                "url",
                "images",
                "attributes",
                "companyId",
                "branchId"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "product"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_similar_products",
        "title": "Get Similar Products",
        "description": "Find products similar to a given product. Use to suggest alternatives.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id"
            },
            "slug": {
              "type": "string",
              "description": "Product slug"
            },
            "limit": {
              "description": "Max results",
              "type": "number"
            },
            "offset": {
              "description": "Offset for pagination",
              "type": "number"
            },
            "deliveryType": {
              "description": "Delivery type from silpo_get_shopping_cart_by_id",
              "type": "string"
            }
          },
          "required": [
            "branchId",
            "slug"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "products": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "name": {
                    "type": "string"
                  },
                  "slug": {
                    "type": "string"
                  },
                  "price": {
                    "type": "number"
                  },
                  "oldPrice": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "stock": {
                    "type": "number"
                  },
                  "available": {
                    "type": "boolean"
                  },
                  "image": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "weighted": {
                    "type": "boolean"
                  },
                  "step": {
                    "type": "number"
                  },
                  "specialPrices": {
                    "anyOf": [
                      {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "properties": {
                            "price": {
                              "type": "number"
                            },
                            "count": {
                              "type": "number"
                            },
                            "type": {
                              "type": "string"
                            }
                          },
                          "required": [
                            "price",
                            "count",
                            "type"
                          ],
                          "additionalProperties": false
                        }
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "companyId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "branchId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "externalProductId": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "name",
                  "slug",
                  "price",
                  "oldPrice",
                  "stock",
                  "available",
                  "image",
                  "weighted",
                  "step",
                  "specialPrices",
                  "companyId",
                  "branchId",
                  "externalProductId"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "products",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_replacements",
        "title": "Get Replacements",
        "description": "Find replacement products when an item is out of stock.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id"
            },
            "companyId": {
              "type": "string",
              "description": "Company ID"
            },
            "productIds": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "Product IDs to find replacements for"
            },
            "deliveryType": {
              "type": "string",
              "description": "Delivery type from silpo_get_shopping_cart_by_id"
            }
          },
          "required": [
            "branchId",
            "companyId",
            "productIds",
            "deliveryType"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "items": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "productId": {
                    "type": "string"
                  },
                  "replacements": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "id": {
                          "type": "string"
                        },
                        "name": {
                          "type": "string"
                        },
                        "slug": {
                          "type": "string"
                        },
                        "price": {
                          "type": "number"
                        },
                        "stock": {
                          "type": "number"
                        },
                        "available": {
                          "type": "boolean"
                        },
                        "image": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "weighted": {
                          "type": "boolean"
                        },
                        "step": {
                          "type": "number"
                        },
                        "companyId": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "branchId": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        }
                      },
                      "required": [
                        "id",
                        "name",
                        "slug",
                        "price",
                        "stock",
                        "available",
                        "image",
                        "weighted",
                        "step",
                        "companyId",
                        "branchId"
                      ],
                      "additionalProperties": false
                    }
                  }
                },
                "required": [
                  "productId",
                  "replacements"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "items"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_coupons",
        "title": "Get My Coupons",
        "description": "List available coupons for the authenticated user.",
        "inputSchema": {
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "coupons": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "number"
                  },
                  "active": {
                    "type": "boolean"
                  },
                  "useWay": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "beginDate": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "endDate": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "description": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "limitText": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "warningText": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "image": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "active",
                  "useWay",
                  "beginDate",
                  "endDate",
                  "description",
                  "limitText",
                  "warningText",
                  "image"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "coupons"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_loyalty_info",
        "title": "Get Loyalty Info",
        "description": "Get loyalty card info and balance for the authenticated user.",
        "inputSchema": {
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "loyalty": {
              "type": "object",
              "properties": {
                "card": {
                  "anyOf": [
                    {
                      "type": "object",
                      "properties": {
                        "barcode": {
                          "type": "string"
                        },
                        "typeName": {
                          "type": "string"
                        },
                        "memberId": {
                          "type": "number"
                        }
                      },
                      "required": [
                        "barcode",
                        "typeName",
                        "memberId"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "balance": {
                  "anyOf": [
                    {
                      "type": "object",
                      "properties": {
                        "total": {
                          "type": "number"
                        },
                        "currency": {
                          "type": "string"
                        },
                        "accounts": {
                          "type": "array",
                          "items": {
                            "type": "object",
                            "properties": {
                              "type": {
                                "type": "string"
                              },
                              "amount": {
                                "type": "number"
                              }
                            },
                            "required": [
                              "type",
                              "amount"
                            ],
                            "additionalProperties": false
                          }
                        }
                      },
                      "required": [
                        "total",
                        "currency",
                        "accounts"
                      ],
                      "additionalProperties": false
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "card",
                "balance"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "loyalty"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_coupon_details",
        "title": "Get Coupon Details",
        "description": "Get detailed info about a specific coupon by its ID (from silpo_get_my_coupons).",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "businessCouponId": {
              "type": "number",
              "description": "Coupon ID from silpo_get_my_coupons"
            }
          },
          "required": [
            "businessCouponId"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "coupon": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "number"
                },
                "active": {
                  "type": "boolean"
                },
                "state": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "useWay": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "beginDate": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "endDate": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "usedCount": {
                  "type": "number"
                },
                "description": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "limitText": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "warningText": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "rewardText": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "rewardValue": {
                  "anyOf": [
                    {
                      "type": "number"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "image": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "id",
                "active",
                "state",
                "useWay",
                "beginDate",
                "endDate",
                "usedCount",
                "description",
                "limitText",
                "warningText",
                "rewardText",
                "rewardValue",
                "image"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "coupon"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_delivery_addresses",
        "title": "Get My Delivery Addresses",
        "description": "Get saved delivery addresses for the authenticated user. Use coordinates from an address with silpo_get_available_delivery_types to set up delivery.",
        "inputSchema": {
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "addresses": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "tag": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "city": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "street": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "building": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "apartment": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "floor": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "entrance": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "latitude": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "longitude": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "comment": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "tag",
                  "city",
                  "street",
                  "building",
                  "apartment",
                  "floor",
                  "entrance",
                  "latitude",
                  "longitude",
                  "comment"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "addresses"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_food_restrictions",
        "title": "Get My Food Restrictions",
        "description": "Get user food restrictions (gluten-free, lactose-free, vegan, etc.). Use to personalize product recommendations.",
        "inputSchema": {
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "restrictions": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "slug": {
                    "type": "string"
                  },
                  "name": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "slug",
                  "name"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "restrictions"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_profile",
        "title": "Get My Profile",
        "description": "Get the authenticated user profile info (name, phone, email, birthday).",
        "inputSchema": {
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "profile": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "string"
                },
                "firstName": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "lastName": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "middleName": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "phone": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "email": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "birthday": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "gender": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                },
                "status": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ]
                }
              },
              "required": [
                "id",
                "firstName",
                "lastName",
                "middleName",
                "phone",
                "email",
                "birthday",
                "gender",
                "status"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "profile"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_promos",
        "title": "Get My Promos",
        "description": "Get personal promotional offers available for selection. User can choose which promos to activate for bonus rewards.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "promos": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "promoId": {
                    "type": "number"
                  },
                  "selected": {
                    "type": "boolean"
                  },
                  "beginDate": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "endDate": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "description": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "rewardText": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "rewardValue": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "limitText": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "warningText": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "addressListText": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "image": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "promoId",
                  "selected",
                  "beginDate",
                  "endDate",
                  "description",
                  "rewardText",
                  "rewardValue",
                  "limitText",
                  "warningText",
                  "addressListText",
                  "image"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "total": {
                  "type": "number"
                },
                "minSelect": {
                  "type": "number"
                },
                "maxSelect": {
                  "type": "number"
                }
              },
              "required": [
                "total",
                "minSelect",
                "maxSelect"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "promos",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_promo_codes",
        "title": "Get Promo Codes",
        "description": "Get promo codes for the authenticated user.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "promoCodes": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "code": {
                    "type": "string"
                  },
                  "title": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "active": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "id",
                  "code",
                  "title",
                  "active"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "promoCodes",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_list_branches",
        "title": "List Silpo Branches",
        "description": "List available Silpo branches with pagination. Use with hasPickup=true when user wants SelfPickup delivery — show 5 nearest branches to their location and let them choose. Branch data (branchId, companyId, latitude, longitude, address, city) is needed to construct the SelfPickup address for silpo_update_shopping_cart.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "limit": {
              "description": "Max results to return (default: 50)",
              "type": "integer",
              "minimum": -9007199254740991,
              "maximum": 9007199254740991
            },
            "offset": {
              "description": "Offset for pagination",
              "type": "integer",
              "minimum": -9007199254740991,
              "maximum": 9007199254740991
            },
            "hasPickup": {
              "description": "Filter branches that support self-pickup",
              "type": "boolean"
            },
            "hasNP": {
              "description": "Filter branches that support Nova Poshta delivery",
              "type": "boolean"
            }
          }
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "branches": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "branchId": {
                    "type": "string"
                  },
                  "companyId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "externalId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "city": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "address": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "latitude": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "longitude": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "hasPickup": {
                    "anyOf": [
                      {
                        "type": "boolean"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "open": {
                    "anyOf": [
                      {
                        "type": "boolean"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "branchId",
                  "companyId",
                  "externalId",
                  "city",
                  "address",
                  "latitude",
                  "longitude",
                  "hasPickup",
                  "open"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "limit": {
                  "type": "number"
                },
                "offset": {
                  "type": "number"
                },
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "limit",
                "offset",
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "branches",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_product_sets",
        "title": "Get Product Sets",
        "description": "Get curated product collections/sets at a Silpo branch. Use slug with silpo_get_products (set param) to browse products in a set.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id or silpo_get_available_delivery_types"
            },
            "deliveryType": {
              "description": "Filter by delivery type",
              "type": "string"
            }
          },
          "required": [
            "branchId"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "sets": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "slug": {
                    "type": "string"
                  },
                  "title": {
                    "type": "string"
                  },
                  "description": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "link": {
                    "type": "string"
                  }
                },
                "required": [
                  "slug",
                  "title",
                  "description",
                  "link"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "sets"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_family",
        "title": "Get My Family",
        "description": "Get family info: household members, children, and pets. Helps personalize product recommendations.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "name": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ]
            },
            "members": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "profileId": {
                    "type": "string"
                  },
                  "name": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "phone": {
                    "type": "string"
                  },
                  "image": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "profileCreatedAt": {
                    "type": "string"
                  },
                  "itsMe": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "profileId",
                  "name",
                  "phone",
                  "image",
                  "profileCreatedAt",
                  "itsMe"
                ],
                "additionalProperties": false
              }
            },
            "children": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "name": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "slug": {
                    "type": "string"
                  },
                  "dateOfBirth": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "name",
                  "slug",
                  "dateOfBirth"
                ],
                "additionalProperties": false
              }
            },
            "pets": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "name": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "slug": {
                    "type": "string"
                  }
                },
                "required": [
                  "id",
                  "name",
                  "slug"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "name",
            "members",
            "children",
            "pets"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_available_delivery_types",
        "title": "Get Available Delivery Types",
        "description": "Get all available delivery types for a location. Returns which delivery types are available at given coordinates with branchId for polygon-based options.\n\nUSE: Pass deliveryType + branchId to silpo_update_shopping_cart or silpo_get_time_slots.\n\nNEXT STEPS BY TYPE:\n- DeliveryHome/WideAssortDelivery/B2B: branchId is provided, use directly\n- SelfPickup: branchId is null → call silpo_list_branches(hasPickup=true) to let user pick a branch\n- NovaPoshta: branchId is null → call silpo_find_nova_poshta_settlements → silpo_find_nova_poshta_offices → silpo_list_branches(hasNP=true) for branchId",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "latitude": {
              "type": "number",
              "description": "Latitude coordinate"
            },
            "longitude": {
              "type": "number",
              "description": "Longitude coordinate"
            }
          },
          "required": [
            "latitude",
            "longitude"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "options": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "deliveryType": {
                    "type": "string"
                  },
                  "branchId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "description": {
                    "type": "string"
                  }
                },
                "required": [
                  "deliveryType",
                  "branchId",
                  "description"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "options"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_find_nova_poshta_settlements",
        "title": "Find Nova Poshta Delivery Cities",
        "description": "Search for cities available for Nova Poshta delivery. Returns settlement IDs needed for silpo_find_nova_poshta_offices.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "title": {
              "type": "string",
              "description": "City name to search for (e.g. \"Київ\", \"Одеса\")"
            }
          },
          "required": [
            "title"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "settlements": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "title": {
                    "type": "string"
                  },
                  "area": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "region": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "title",
                  "area",
                  "region"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "settlements"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_find_nova_poshta_offices",
        "title": "Find Nova Poshta Offices",
        "description": "Search for Nova Poshta offices/parcel lockers in a settlement.\n\nUSE: After silpo_find_nova_poshta_settlements. Pass offices[].id, offices[].latitude, offices[].longitude, offices[].type, offices[].number to construct NovaPoshta address for silpo_update_shopping_cart.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "settlementId": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
              "description": "Settlement ID from silpo_find_nova_poshta_settlements"
            },
            "title": {
              "description": "Filter by office number or address text",
              "type": "string"
            }
          },
          "required": [
            "settlementId"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "offices": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "title": {
                    "type": "string"
                  },
                  "address": {
                    "type": "string"
                  },
                  "type": {
                    "type": "string"
                  },
                  "number": {
                    "type": "number"
                  },
                  "status": {
                    "type": "string"
                  },
                  "latitude": {
                    "type": "number"
                  },
                  "longitude": {
                    "type": "number"
                  }
                },
                "required": [
                  "id",
                  "title",
                  "address",
                  "type",
                  "number",
                  "status",
                  "latitude",
                  "longitude"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "offices",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_offline_orders",
        "title": "Get My Offline Orders",
        "description": "View in-store (offline) purchase history from physical Silpo shops.\n\nUnlike silpo_get_my_online_orders (website/app orders), this shows purchases made at physical store checkouts using the loyalty card.\n\nREQUIRES: branchId, deliveryType, timeslotStart, timeslotEnd from silpo_get_shopping_cart_by_id to check product availability.\n\nRESPONSE: Products with catalogProduct !== null can be reordered via silpo_add_or_update_cart_products. Products with catalogProduct === null — use silpo_find_products_batch with product name to find replacements.\n\nHIGHLIGHT FOR USER:\n- accruedBalaBonusesSum — Балабонуси earned for this order. Show this to the user as a benefit of shopping at Silpo.\n- rewards[] — promotions/coupons that were applied to this order and saved money. Highlight these to show how the user benefited.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id"
            },
            "deliveryType": {
              "type": "string",
              "description": "Delivery type from silpo_get_shopping_cart_by_id"
            },
            "timeslotStart": {
              "type": "string",
              "description": "Timeslot start from silpo_get_shopping_cart_by_id"
            },
            "timeslotEnd": {
              "type": "string",
              "description": "Timeslot end from silpo_get_shopping_cart_by_id"
            },
            "limit": {
              "description": "Max orders to return (default: 10, max: 10)",
              "type": "integer",
              "minimum": 1,
              "maximum": 10
            },
            "offset": {
              "description": "Skip for pagination (default: 0)",
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            "dateStart": {
              "description": "Period start in ISO format (default: 6 months ago)",
              "type": "string"
            },
            "dateEnd": {
              "description": "Period end in ISO format (default: now)",
              "type": "string"
            }
          },
          "required": [
            "branchId",
            "deliveryType",
            "timeslotStart",
            "timeslotEnd"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "orders": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "filId": {
                    "type": "number"
                  },
                  "filialName": {
                    "type": "string"
                  },
                  "cityName": {
                    "type": "string"
                  },
                  "createdAt": {
                    "type": "string"
                  },
                  "sumReg": {
                    "type": "number"
                  },
                  "accruedBalaBonusesSum": {
                    "type": "number"
                  },
                  "sumDiscount": {
                    "type": "number"
                  },
                  "receiptUrl": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "chequeMagicName": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "chequePrediction": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "rewards": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "rewardGroupCodeName": {
                          "type": "string"
                        },
                        "applyText": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "valueText": {
                          "type": "string"
                        },
                        "applyRewardAmount": {
                          "type": "number"
                        },
                        "promoId": {
                          "anyOf": [
                            {
                              "type": "number"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        }
                      },
                      "required": [
                        "rewardGroupCodeName",
                        "applyText",
                        "valueText",
                        "applyRewardAmount",
                        "promoId"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "products": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "lagerId": {
                          "type": "number"
                        },
                        "name": {
                          "type": "string"
                        },
                        "unit": {
                          "type": "string"
                        },
                        "quantity": {
                          "type": "number"
                        },
                        "price": {
                          "type": "number"
                        },
                        "image": {
                          "anyOf": [
                            {
                              "type": "string"
                            },
                            {
                              "type": "null"
                            }
                          ]
                        },
                        "catalogProduct": {
                          "anyOf": [
                            {
                              "type": "object",
                              "properties": {
                                "id": {
                                  "type": "string"
                                },
                                "name": {
                                  "type": "string"
                                },
                                "slug": {
                                  "type": "string"
                                },
                                "price": {
                                  "type": "number"
                                },
                                "stock": {
                                  "type": "number"
                                },
                                "available": {
                                  "type": "boolean"
                                },
                                "image": {
                                  "anyOf": [
                                    {
                                      "type": "string"
                                    },
                                    {
                                      "type": "null"
                                    }
                                  ]
                                },
                                "weighted": {
                                  "type": "boolean"
                                },
                                "step": {
                                  "type": "number"
                                },
                                "companyId": {
                                  "type": "string"
                                },
                                "branchId": {
                                  "type": "string"
                                }
                              },
                              "required": [
                                "id",
                                "name",
                                "slug",
                                "price",
                                "stock",
                                "available",
                                "image",
                                "weighted",
                                "step",
                                "companyId",
                                "branchId"
                              ],
                              "additionalProperties": false
                            },
                            {
                              "type": "null"
                            }
                          ]
                        }
                      },
                      "required": [
                        "lagerId",
                        "name",
                        "unit",
                        "quantity",
                        "price",
                        "image",
                        "catalogProduct"
                      ],
                      "additionalProperties": false
                    }
                  }
                },
                "required": [
                  "filId",
                  "filialName",
                  "cityName",
                  "createdAt",
                  "sumReg",
                  "accruedBalaBonusesSum",
                  "sumDiscount",
                  "receiptUrl",
                  "chequeMagicName",
                  "chequePrediction",
                  "rewards",
                  "products"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "limit": {
                  "type": "number"
                },
                "offset": {
                  "type": "number"
                },
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "limit",
                "offset",
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "orders",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_certificates",
        "title": "Get My Certificates",
        "description": "Get user gift certificates that can be applied to the shopping cart. Shows barcode, pincode, expiry date and value.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "limit": {
              "description": "Max certificates to return (default: 50)",
              "type": "integer",
              "minimum": 1,
              "maximum": 100
            },
            "offset": {
              "description": "Pagination offset (default: 0)",
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            }
          }
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "certificates": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "number"
                  },
                  "createdAt": {
                    "type": "string"
                  },
                  "totalPrice": {
                    "type": "number"
                  },
                  "barcode": {
                    "type": "string"
                  },
                  "pincode": {
                    "anyOf": [
                      {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "number"
                          }
                        ]
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "expireDate": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "title": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "image": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "createdAt",
                  "totalPrice",
                  "barcode",
                  "pincode",
                  "expireDate",
                  "title",
                  "image"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "certificates"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_premium_subscription",
        "title": "Get My Premium Subscription",
        "description": "Get premium subscription (Плюхс) details including features, balances, and benefits. Shows active subscription status, available bonuses, and feature cards with links.\n\nIf subscription is NOT active: ALWAYS show BOTH links to the user — webLink labeled \"Оформити на сайті\" and mobileLink labeled \"Оформити в застосунку\".\n\nIf subscription IS active: ALWAYS show BOTH share links — shareWebLink labeled \"Поділитись (сайт)\" and shareMobileLink labeled \"Поділитись (застосунок)\".",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {}
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "webLink": {
              "type": "string"
            },
            "mobileLink": {
              "type": "string"
            },
            "id": {
              "type": "string"
            },
            "profileId": {
              "type": "string"
            },
            "subscriptionId": {
              "type": "string"
            },
            "createdAt": {
              "type": "string"
            },
            "status": {
              "type": "string"
            },
            "dateFrom": {
              "type": "string"
            },
            "dateTo": {
              "type": "string"
            },
            "features": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "business": {
                    "type": "string"
                  },
                  "name": {
                    "type": "string"
                  },
                  "checkoutText": {
                    "type": "string"
                  },
                  "image": {
                    "type": "string"
                  },
                  "balance": {
                    "anyOf": [
                      {
                        "type": "object",
                        "properties": {
                          "total": {
                            "type": "string"
                          },
                          "available": {
                            "type": "string"
                          },
                          "type": {
                            "anyOf": [
                              {
                                "type": "string"
                              },
                              {
                                "type": "null"
                              }
                            ]
                          }
                        },
                        "required": [
                          "total",
                          "available",
                          "type"
                        ],
                        "additionalProperties": false
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "webLink": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "mobileLink": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "descriptionHtml": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "business",
                  "name",
                  "checkoutText",
                  "image",
                  "balance",
                  "webLink",
                  "mobileLink",
                  "descriptionHtml"
                ],
                "additionalProperties": false
              }
            },
            "bonusesObtainedAmount": {
              "type": "number"
            },
            "shareWebLink": {
              "type": "string"
            },
            "shareMobileLink": {
              "type": "string"
            }
          },
          "required": [
            "success",
            "summary"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_get_my_favorites",
        "title": "Get My Favorites",
        "description": "Get the user's favorite products at a Silpo branch. Returns products in the same format as silpo_get_products — use companyId, branchId, id, and step to add items to cart via silpo_add_or_update_cart_products.\n\nAll inputs must be taken from silpo_get_shopping_cart_by_id: branchId, deliveryType, timeslotStart (slot.start).",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "branchId": {
              "type": "string",
              "description": "Branch ID from silpo_get_shopping_cart_by_id"
            },
            "deliveryType": {
              "type": "string",
              "enum": [
                "Unknown",
                "SelfPickup",
                "DeliveryHome",
                "DeliveryFlat",
                "DeliveryOffice",
                "DeliveryGlovo",
                "DeliveryExpress",
                "DeliveryExpressFood",
                "JustIn",
                "LongDelivery",
                "JustInPost",
                "NovaPoshta",
                "DeliveryExpressByPromise",
                "WideAssortDelivery"
              ],
              "description": "Delivery type from silpo_get_shopping_cart_by_id"
            },
            "timeslotStart": {
              "type": "string",
              "description": "Timeslot start ISO timestamp from silpo_get_shopping_cart_by_id slot.start"
            },
            "limit": {
              "description": "Max results (default: 25)",
              "type": "integer",
              "minimum": 1,
              "maximum": 500
            },
            "offset": {
              "description": "Pagination offset (default: 0)",
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            }
          },
          "required": [
            "branchId",
            "deliveryType",
            "timeslotStart"
          ]
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "products": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string"
                  },
                  "name": {
                    "type": "string"
                  },
                  "slug": {
                    "type": "string"
                  },
                  "price": {
                    "type": "number"
                  },
                  "oldPrice": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "stock": {
                    "type": "number"
                  },
                  "available": {
                    "type": "boolean"
                  },
                  "image": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "weighted": {
                    "type": "boolean"
                  },
                  "step": {
                    "type": "number"
                  },
                  "specialPrices": {
                    "anyOf": [
                      {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "properties": {
                            "price": {
                              "type": "number"
                            },
                            "count": {
                              "type": "number"
                            },
                            "type": {
                              "type": "string"
                            }
                          },
                          "required": [
                            "price",
                            "count",
                            "type"
                          ],
                          "additionalProperties": false
                        }
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "companyId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "branchId": {
                    "anyOf": [
                      {
                        "type": "string"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "externalProductId": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "id",
                  "name",
                  "slug",
                  "price",
                  "oldPrice",
                  "stock",
                  "available",
                  "image",
                  "weighted",
                  "step",
                  "specialPrices",
                  "companyId",
                  "branchId",
                  "externalProductId"
                ],
                "additionalProperties": false
              }
            },
            "meta": {
              "type": "object",
              "properties": {
                "limit": {
                  "type": "number"
                },
                "offset": {
                  "type": "number"
                },
                "total": {
                  "type": "number"
                }
              },
              "required": [
                "limit",
                "offset",
                "total"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "success",
            "summary",
            "products",
            "meta"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_add_or_update_favorite_products",
        "title": "Add/Update Favorite Products",
        "description": "Add or remove products from the user's favorites list.\n\nUse productId and externalProductId from any product-returning tool (silpo_get_my_favorites, silpo_find_products_batch, silpo_get_products, silpo_get_similar_products, etc).\n\nTo ADD: set toDelete=false.\nTo REMOVE: set toDelete=true. Get productId and externalProductId from silpo_get_my_favorites.\n\nMax 5 actions per call.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "actions": {
              "minItems": 1,
              "maxItems": 5,
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "productId": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                    "description": "Product id field from any product-returning tool"
                  },
                  "externalProductId": {
                    "type": "integer",
                    "minimum": -9007199254740991,
                    "maximum": 9007199254740991,
                    "description": "externalProductId field from any product-returning tool"
                  },
                  "toDelete": {
                    "type": "boolean",
                    "description": "true to remove from favorites, false to add"
                  }
                },
                "required": [
                  "productId",
                  "externalProductId",
                  "toDelete"
                ]
              },
              "description": "List of add/remove actions (max 5)"
            }
          },
          "required": [
            "actions"
          ]
        },
        "annotations": {
          "readOnlyHint": false,
          "destructiveHint": false,
          "idempotentHint": false,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "actions": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "productId": {
                    "type": "string"
                  },
                  "toDelete": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "productId",
                  "toDelete"
                ],
                "additionalProperties": false
              }
            }
          },
          "required": [
            "success",
            "summary",
            "actions"
          ],
          "additionalProperties": false
        }
      },
      {
        "name": "silpo_add_or_update_certificates",
        "title": "Add/Remove Cart Certificates",
        "description": "Add or remove gift certificates from the shopping cart in one call. Adds run before removes.\n\ncertificatesToAdd: get barcode and pincode from silpo_get_my_certificates or from user input. Max 10.\ncertificatesToRemove: get barcode from the certificates array in silpo_get_shopping_cart_by_id response. Max 10.\n\nMANDATORY: After calling this tool, ALWAYS call silpo_get_shopping_cart_by_id to verify the result and check if cart total changed.\n\nVALIDATION ERRORS: If added[].validations is non-empty, show the messages to the user — the certificate was not applied.",
        "inputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "shoppingCartId": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
              "description": "Cart ID from silpo_get_my_shopping_cart"
            },
            "certificatesToAdd": {
              "description": "Certificates to add (barcode + optional pincode)",
              "maxItems": 10,
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "barcode": {
                    "type": "string",
                    "description": "Certificate barcode"
                  },
                  "pincode": {
                    "description": "Certificate PIN (required for gift certificates)",
                    "type": "string"
                  }
                },
                "required": [
                  "barcode"
                ]
              }
            },
            "certificatesToRemove": {
              "description": "Certificates to remove (barcode from silpo_get_shopping_cart_by_id certificates)",
              "maxItems": 10,
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "barcode": {
                    "type": "string",
                    "description": "Certificate barcode"
                  },
                  "pincode": {
                    "description": "Certificate PIN (required for gift certificates)",
                    "type": "string"
                  }
                },
                "required": [
                  "barcode"
                ]
              }
            }
          },
          "required": [
            "shoppingCartId"
          ]
        },
        "annotations": {
          "readOnlyHint": false,
          "destructiveHint": false,
          "idempotentHint": false,
          "openWorldHint": true
        },
        "execution": {
          "taskSupport": "forbidden"
        },
        "outputSchema": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean"
            },
            "summary": {
              "type": "string"
            },
            "added": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "barcode": {
                    "type": "string"
                  },
                  "faceValue": {
                    "anyOf": [
                      {
                        "type": "number"
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "validations": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "type": {
                          "type": "string"
                        },
                        "level": {
                          "type": "string"
                        },
                        "message": {
                          "type": "string"
                        }
                      },
                      "required": [
                        "type",
                        "level",
                        "message"
                      ],
                      "additionalProperties": false
                    }
                  }
                },
                "required": [
                  "barcode",
                  "faceValue",
                  "validations"
                ],
                "additionalProperties": false
              }
            },
            "removed": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          },
          "required": [
            "success",
            "summary",
            "added",
            "removed"
          ],
          "additionalProperties": false
        }
      }
    ]
  },
  "jsonrpc": "2.0",
  "id": 3
}


### chain: address -> delivery -> slots -> catalog


#### find_address

{
  "success": true,
  "summary": "Found 12 addresses",
  "addresses": [
    {
      "address": "Київ, вулиця Богдана Хмельницького, 3-Б/1",
      "city": "Київ",
      "street": "вулиця Богдана Хмельницького",
      "houseNumber": "3-Б/1",
      "district": "Центр",
      "latitude": 50.444541099999995,
      "longitude": 30.519500168726374
    },
    {
      "address": "Київ, вулиця Богдана Хмельницького, 27/1",
      "city": "Київ",
      "street": "вулиця Богдана Хмельницького",
      "houseNumber": "27/1",
      "district": "Центр",
      "latitude": 50.4462705,
      "longitude": 30.510603165640596
    },
    {
      "address": "Київська область, Нові Петрівці, вулиця Богдана Хмельницького",
      "city": "Нові Петрівці",
      "street": "вулиця Богдана Хмельницького",
      "houseNumber": null,
      "district": null,
      "latitude": 50.6348527,
      "longitude": 30.4296074
    },
    {
      "address": "Київ, вулиця Богдана Хмельницького, 35/1, Космо",
      "city": "Київ",
      "street": "вулиця Богдана Хмельницького",
      "houseNumber": "35/1",
      "district": "Центр",
      "latitude": 50.4468038,
      "longitude": 30.5075683
    },
    {
      "address": "Київ, вулиця Богдана Хмельницького, 27/1, Herstory",
      "city": "Київ",
      "street": "вулиця Богдана Хмельницького",
      "houseNumber": "27/1",
      "district": "Центр",
      "latitude": 50.4462421,
      "longitude": 30.5107548
    },
    {
      "address": "Київська область, Хотів, вулиця Бог


#### available_delivery_types

{
  "success": true,
  "summary": "Found 5 delivery options for 50.444541099999995, 30.519500168726374",
  "options": [
    {
      "deliveryType": "DeliveryHome",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "description": "Regular delivery (groceries, fresh products)"
    },
    {
      "deliveryType": "WideAssortDelivery",
      "branchId": "1f05d7b8-27b0-6762-8aea-896c4e98f56d",
      "description": "Wide assortment delivery (extended product range)"
    },
    {
      "deliveryType": "B2B",
      "branchId": "1ee11bac-502d-6cd6-bd9d-7921cac13a23",
      "description": "B2B delivery (business orders)"
    },
    {
      "deliveryType": "NovaPoshta",
      "branchId": null,
      "description": "Nova Poshta delivery (shipped via Nova Poshta)"
    },
    {
      "deliveryType": "SelfPickup",
      "branchId": null,
      "description": "Self pickup from a Silpo store"
    }
  ]
}


#### time_slots

{
  "success": true,
  "summary": "Found 8 time slots (8 available)",
  "slots": [
    {
      "start": "2026-08-07T06:00:00+00:00",
      "end": "2026-08-07T07:30:00+00:00",
      "available": true,
      "deliveryType": "DeliveryHome",
      "deliveryCost": 99,
      "deliveryCostMap": [
        {
          "cost": 69,
          "fromOrderCost": 1299
        },
        {
          "cost": 1,
          "fromOrderCost": 1899
        }
      ],
      "minOrderCost": 699,
      "maxWeight": 30,
      "constraints": {
        "isLimitedAlcohol": false,
        "isLimitedTobacco": false,
        "isLimitedCookedFood": true,
        "isLimitedOwnCooking": true
      },
      "fast": null
    },
    {
      "start": "2026-08-07T07:30:00+00:00",
      "end": "2026-08-07T09:00:00+00:00",
      "available": true,
      "deliveryType": "DeliveryHome",
      "deliveryCost": 99,
      "deliveryCostMap": [
        {
          "cost": 69,
          "fromOrderCost": 1299
        },
        {
          "cost": 1,
          "fromOrderCost": 1899
        }
      ],
      "minOrderCost": 699,
      "maxWeight": 30,
      "constraints": {
        "isLimitedAlcohol": false,
        "isLimitedTobacco": false,
        "isLimitedCookedFood": false,
        "isLimitedOwnCooking": false
      },
      "fast": null
    },
    {
      "start": "2026-08-07T09:00:00+00:00",
      "end": "2026-08-07T10:30:00+00:00",
      "available": true,
      "deliveryType": "DeliveryHome",
      "deliveryCost": 99,
      "deliveryCostMap": [
        {
          "cost": 69,
          "fromOrderCost": 1299
        },
        {
          "cost": 1,
          "fromOrderCost": 1899
        }
      ],
      "minOrderCost": 699,
      "maxWeight": 30,
      "constraints": {
        "isLimitedAlcohol": false,
        "isLimitedTobacco": false,
        "isLimitedCookedFood": false,
        "isLimitedOwnCooking": false
      },
      "fast": null
    },
    {
      "start": "2026-08-07T10:30:00+00:00",
      "end": "2026-08-07T12:00:00+00:00",
      "available": true,
      "deliveryType": "DeliveryHome",
      "deliveryCost": 99,
      "deliveryCostMap": [
        {
          "cost": 69,
          "fromOrderCost": 1299
        },
        {
          "cost": 1,
          "fromOrderCost": 1899
        }
      ],
      "minOrderCost": 699,
      "maxWeight": 30,
      "constraints": {
        "isLimitedAlcohol": false,
        "isLimitedTobacco": false,
        "isLimitedCookedFood": false,
        "isLimitedO


#### resolved context: {"branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564", "deliveryType": "DeliveryHome", "timeslotStart": "2026-08-07T06:00:00+00:00", "timeslotEnd": "2026-08-07T07:30:00+00:00"}


#### categories_top

{
  "success": true,
  "summary": "Found 1000 categories (total: 1015)",
  "categories": [
    {
      "id": "1edb13cb-d304-6fea-be02-53f89724fa3a",
      "slug": "shokoladni-figurky-524",
      "title": "Шоколадні фігурки",
      "parentId": "1edb13bf-6b4e-6830-8a12-53f89724fa3a"
    },
    {
      "id": "1edb13e4-d93e-66e0-bbc2-53f89724fa3a",
      "slug": "gorikhy-v-syropi-517",
      "title": "Горіхи в сиропі",
      "parentId": "1edb13c5-9368-61b2-bd05-53f89724fa3a"
    },
    {
      "id": "1edb13c0-69c3-6622-b5d4-53f89724fa3a",
      "slug": "yaitsia-528",
      "title": "Яйця",
      "parentId": "1edb13bf-5d61-64d4-992b-53f89724fa3a"
    },
    {
      "id": "1ee3b392-11ae-664c-bea3-d5a21254cccc",
      "slug": "ikra-inshykh-ryb-4447",
      "title": "Ікра інших риб",
      "parentId": "1ee3b391-b529-6c8c-9a7d-d5a21254cccc"
    },
    {
      "id": "1ee3b391-94f1-63c0-b74d-d5a21254cccc",
      "slug": "kuriatyna-4426",
      "title": "Курятина",
      "parentId": "1ee3b391-93fb-63f8-bcd3-d5a21254cccc"
    },
    {
      "id": "1ee3b391-b52d-67f6-bd6a-d5a21254cccc",
      "slug": "chorna-ikra-4446",
      "title": "Чорна ікра",
      "parentId": "1ee3b391-b529-6c8c-9a7d-d5a21254cccc"
    },
    {
      "id": "1ee506fc-e833-6fa0-80e3-c7e4fc354612",
      "slug": "zamorozheni-moreprodukty-ta-moliusky-4451",
      "title": "Заморожені морепродукти та молюски",
      "parentId": "1ee3b391-91da-6b00-8f07-d5a21254cccc"
    },
    {
      "id": "1ee3b391-8799-6182-a7cf-d5a21254cccc",
      "slug": "prygotovana-ta-kopchena-ryba-4433",
      "title": "Приготовлена риба, салати і пресерви",
      "parentId": "1ee3b391-8794-6e66-a421-d5a21254cccc"
    },
    {
      "id": "1edb13d0-8e41-67e6-8cd0-53f89724fa3a",
      "slug": "grunty-dobryva-480",
      "title": "Ґрунти, добрива",
      "parentId": "1edb13d0-8e3d-651a-9a07-53f89724fa3a"
    },
    {
      "id": "1ee506fc-dc74-61b0-88fc-c7e4fc354612",
      "slug": "okholodzheni-moreprodukty-ta-moliusky-4450",
      "title": "Охолоджені морепродукти та молюски",
      "parentId": "1ee3b391-91da-6b00-8f07-d5a21254cccc"
    },
    {
      "id": "1edb13c1-3b4f-627c-9f68-53f89724fa3a",
      "slug": "moloko-253",
      "title": "Молоко",
      "parentId": "1edb13bf-5d7a-6808-8e07-53f89724fa3a"
    },
    {
      "id": "1ee3b393-a105-6466-b446-d5a21254cccc",
      "slug": "chervona-ikra-4445",
      "title": "Червона ікра",
      "parentId": "1ee3b391-b529-6c8c-9a7d-d5a21254cccc"
    },
    {
      "id": "1edb13c4-999c-684a-aba5-53f89724fa3a",
      "slug": "biskvity-molochni-241",
      "title": "Бісквіти молочні",
      "parentId": "1edb13c1-34c9-65b0-a10a-53f89724fa3a"
    },
    {
      "id": "1ee3b391-879c-6e72-9ee1-d5a21254cccc",
      "slug": "slabosolena-ryba-4441",
      "title": "Слабосолена риба",
      "parentId": "1ee3b391-8799-6182-a7cf-d5a21254cccc"
    },
    {
      "id": "1ee878e8-dd00-60aa-a6f7-818c059642bd",
      "slug": "steiky-4457",
      "title": "Стейки",
      "parentId": "1ee3b39


#### categories_tree

{
  "success": true,
  "summary": "Found 28 top-level categories",
  "tree": [
    {
      "slug": "spetsialni-propozytsii-5189",
      "children": [
        {
          "slug": "50-povertayemo-balobonusamy",
          "children": [
            {
              "slug": "kosmetyka-tm-maybelline-ny",
              "children": []
            },
            {
              "slug": "zasoby-dlia-dohliadu-tm-mrs-scrubber",
              "children": []
            }
          ]
        },
        {
          "slug": "ptaaak-na-zheleini-tsukerky",
          "children": [],
          "total": 84
        },
        {
          "slug": "tilky-onlain-znyzhky-na-vlasni-torhovi-marky",
          "children": [],
          "total": 67
        },
        {
          "slug": "ptaaak-na-dytiachu-molochnu-produktsiyu",
          "children": [],
          "total": 26
        },
        {
          "slug": "ptaaak-na-pyvo-ta-sneky-vlasnoho-importu",
          "children": [
            {
              "slug": "gyvo-ukraina-ta-import",
              "children": [],
              "total": 397
            },
            {
              "slug": "sneky-vlasnoho-importu",
              "children": [],
              "total": 124
            }
          ],
          "total": 521
        },
        {
          "slug": "plius-na-zhyttia-5043",
          "children": [
            {
              "slug": "1d3d58f2e1e5460d3a81a31fd1f61dee",
              "children": [],
              "total": 137
            },
            {
              "slug": "9e17b9fdf887c88029f4f6ee0e813b83",
              "children": []
            },
            {
              "slug": "f98973d6a256b81fc4ec76d87b85f2d0",
              "children": []
            },
            {
              "slug": "9cf9f500038ff6026e23a8eb4287df5f",
              "children": []
            }
          ],
          "total": 137
        }
      ],
      "total": 834
    },
    {
      "slug": "frukty-ovochi-4788",
      "children": [
        {
          "slug": "sezonni-ovochi-frukty-4789",
          "children": [],
          "total": 34
        },
        {
          "slug": "frukty-4791",
          "children": [
            {
              "slug": "banany-4792",
              "children": [],
              "total": 5
            },
            {
              "slug": "tsytrusovi-4804",
              "children": [],
              "total": 5
            },
            {
              "slug": "grushi-4795",
              "children": [],
              "total": 2
            },
            {
              "slug": "yabluka-4805",
              "children": [],
              "total": 8
            },
            {
              "slug": "vynograd-4793",
              "children": [],
              "total": 7
            },
            {
              "slug": "granat-4794",
              "children": [],
              "total": 1
            },
            {
              "slug": "kivi-4797",
              "children": [],
              "total": 2
            },
            {
              "slug": "khurma-4803",
              "children": []
            },
            {
              "slug": "kokos-4798",
              "children": [],
              "total": 2
            },
            {
              "slug": "mango-4799",
              "children": [],
              "total": 2
            },
            {
              "slug": "persyky-abrykosy-slyvy-4800",
              "children": [],
              "total": 17
            },
            {
              "slug": "chereshni-vyshni-4801",
              "children": [],
              "total": 2
            },
            {
              "slug": "kavuny-i-dyni-4796",
              "children": [],
              "total": 13
            },
            {
              "slug": "tropichni-frukty-4802",
              "children": [],
              "total": 19
            }
          ],
          "total": 81
        },
        {
          "slug": "yagody-4806",
          "children": [],
          "total": 23
        },
        {
          "slug": "ovochi-4808",
          "children": [
            {
              "slug": "avokado-4810",
              "children": [],
              "total": 4
            },
            {
              "slug": "ogirky-4823",
              "children": [],
              "total": 6
            },
            {
              "slug": "pomidory-4825",
              "children": [],
              "total": 29
            },
            {
              "slug": "kapusta-4813",
              "children": [],
              "total": 16
            },
            {
              "slug": "perets-4824",
              "children": [],
              "total": 15
            },
            {
              "slug": "kartoplia-i-batat-4817",
              "children": [],
              "total": 8
            },
            {
              "slug": "morkva-4818",
              "children": [],
              "total": 6
            },
            {
              "slug": "buriak-4819",
              "children": [],
              "total": 4
            },
            {
              "slug": "tsybulia-i-chasnyk-4826",
              "children": [],
              "total": 18
            },
            {
              "slug": "redyska-redka-koreneplody-4820",
              "children": [],
              "total": 4
            },
            {
              "slug": "baklazhany-4809",
              "children": [],
              "total": 2
            },
            {
              "slug": "kabachky-tsukini-4811",
              "children": [],
              "total": 6
            },
            {
              "slug": "garbuz-4812",
              "children": [],
              "total": 2
            },
            {
              "slug": "sparzha-4814",
              "children": []
            },
            {
              "slug": "kvasolia-sparzheva-4815",
              "children": [],
              "total": 1
            },
            {
              "slug": "gorokh-molodyi-4816",
              "children": [],
              "total": 1
            },
            {
              "slug": "kukurudza-4822",
              "children": [],
              "total": 2
            },
            {
              "slug": "imbyr-4821",
              "children": [],
              "total": 2
            },
            {
              "slug": "ovochevi-nabory-4828",
              "children": [],
              "total": 1
            },
            {
              "slug": "mini-ovochi-4827",
              "children": [],
              "total": 10
            },
            {
              "slug": "artyshok-4862",
              "children": [],
              "total": 1
            }
          ],
          "total": 128
        },
        {
          "slug": "zelen-i-salaty-4829",
          "children": [
            {
              "slug": "mikrogrin-4830",
              "children": [],
              "total": 18
            },
            {
              "slug": "salaty-4831",
              "children": [],
              "total": 39
            },
            {
              "slug": "salaty-z-dodatkamy-4832",
              "children": []
            },
            {
              "slug": "bazylik-4833",
              "children": [],
              "total": 7
            },
            {
              "slug": "zelena-tsybulia-4834",
              "children": [],
              "total": 4
            },
            {
              "slug": "zelen-miks-4835",
              "children": [],
              "total": 2
            },
            {
              "slug": "kinza-4836",
              "children": [],
              "total": 2
            },
            {
              "slug": "krip-4837",
              "children": [],
              "total": 2
            },
            {
              "slug": "m-iata-4838",
              "children": [],
              "total": 3
            },
            {
              "slug": "petrushka-4839",
              "children": [],
              "total": 4
            },
            {
              "slug": "priani-travy-4840",
              "children": [],
              "total": 15
            },
            {
              "slug": "selera-4841",
              "children": [],
              "total": 2
            },
            {
              "slug": "fenkhel-4842",
              "children": [],
              "total": 1
            },
            {
              "slug": "shpynat-4843",
              "children": [],
              "total": 2
            },
            {
              "slug": "shchavel-4844",
              "children": [],
              "total": 2
            },
            {
              "slug": "zelen-v-gorshchyku-4845",
              "children": [],
              "total": 8
            },
            {
              "slug": "revin-5215",
              "children": [],
              "total": 1
            }
          ],
          "total": 103
        },
        {
          "slug": "gryby-4846",
          "children": [
            {
              "slug": "glyvy-4847",
              "children": [],
              "total": 1
            },
            {
              "slug": "ekzotychni-gryby-4848",
              "children": [],
              "total": 10
            },
            {
              "slug": "lisovi-gryby-4849",
              "children": [],
              "total": 1
            },
            {
              "slug": "pecherytsi-4850",
              "children": [],
              "total": 5
            },
            {
              "slug": "susheni-gryby-4851",
              "children": [],
              "total": 13
            }
          ],
          "total": 30
        },
        {
          "slug": "smuzi-i-freshi-4807",
          "children": [],
          "total": 44
        },
        {
          "slug": "fruktovi-ovochevi-sneky-4790",
          "children": [],
          "total": 234
        },
        {
          "slug": "gorikhy-i-sukhofrukty-4853",
          "children": [
            {
              "slug": "gorikhy-4854",
              "children": [],
              "total": 99
            },
            {
              "slug": "nasinnia-i-zerniata-4855",
              "children": [],
              "total": 10
            },
            {
              "slug": "sukhofrukty-i-tsukaty-4856",
              "children": [],
              "total": 100
            },
            {
              "slug": "sumishi-gorikhiv-i-sukhofruktiv-4857",
              "children": [],
              "total": 24
            }
          ],
          "total": 233
        },
        {
          "slug": "solinnia-4852",
          "children": [],
          "total": 42
        }
      ],
      "total": 916
    },
    {
      "slug": "m-iaso-4411",
      "children": [
        {
          "slug": "steiky-4457",
          "children": [],
          "total": 30
        },
        {
          "slug": "m-iaso-dlia-shashlyka-ta-barbekiu-4423",
          "children": [],
          "total": 26
        },
        {
          "slug": "m-iaso-ptytsi-4412",
          "children": [
            {
              "slug": "kuriatyna-4426",
              "children": [],
              "total": 36
            },
            {
              "slug": "indychatyna-4427",
              "children": [],
              "total": 14
            },
            {
              "slug": "kachatyna-ta-gusiatyna-4428",
              "children": [],
              "total": 4
            },
            {
              "slug": "perepilka-4429",
              "children": [],
              "total": 6
            }
          ],
          "total": 60
        },
        {
          "slug": "svynyna-4413",
          "children": [],
          "total": 18
        },
        {
          "slug": "farsh-4419",
          "children": [],
          "total": 4
        },
        {
          "slug": "diietychne-m-iaso-4418",
          "children": [],
          "total": 44
        },
        {
          "slug": "subprodukty-4421",
          "children": [],
          "total": 15
        },
        {
          "slug": "yalovychyna-ta-teliatyna-4414",
          "children": [],
          "total": 64
        },
        {
          "slug": "m-iasni-napivfabrykaty-4422",
          "children": [],
          "total": 10
        },
        {
          "slug": "salo-4420",
          "children": [],
          "total": 1
        },
        {
          "slug": "kroliatyna-4416",
          "children": [],
          "total": 10
        },
        {
          "slug": "baranyna-ta-iagniatyna-4415",
          "children": [],
          "total": 17
        },
        {
          "slug": "dychyna-4417",
          "children": [],
          "total": 1
        }
      ],
      "total": 194
    },
    {
      "slug": "ryba-4430",
      "children": [
        {
          "slug": "prygotovana-ta-kopchena-ryba-4433",
          "children": [
            {
              "slug": "slabosolena-ryba-4441",
              "children": [],
              "total": 28
            },
            {
              "slug": "preservy-rybni-4444",
              "children": [],
              "total": 28
            },
            {
              "slug": "rybni-zakusky-4452",
              "children": [],
              "total": 12
            },
            {
              "slug": "morska-kapusta-ta-salaty-4453",
              "children": [],
              "total": 10
            },
            {
              "slug": "rybni-pasty-4586",
              "children": [],
              "total": 1
            }
          ],
          "total": 98
        },
        {
          "slug": "kopchena-i-v-ialena-ryba-4580",
          "children": [
            {
              "slug": "kopchena-ryba-ta-moreprodukty-4442",
              "children": [],
              "total": 29
            },
            {
              "slug": "v-ialena-ta-sushena-ryba-4443",
              "children": [],
              "total": 13
            }
          ],
          "total": 42
        },
        {
          "slug": "svizha-ryba-4431",
          "children": [
            {
              "slug": "losos-i-forel-4858",
              "children": [],
              "total": 9
            },
            {
              "slug": "morska-ryba-4859",
              "children": [],
              "total": 32
            },
            {
              "slug": "richkova-ryba-4860",
              "children": [],
              "total": 3
            },
            {
              "slug": "zhyva-ryba-4861",
              "children": [],
              "total": 1
            }
          ],
          "total": 48
        },
        {
          "slug": "zamorozhena-ryba-4432",
          "children": [],
          "total": 14
        },
        {
          "slug": "ikra-4439",
          "children": [
            {
              "slug": "ikra-inshykh-ryb-4447",
              "children": [],
              "total": 14
            },
            {
              "slug": "chorna-ikra-4446",
              "children": [],
              "total": 20
            },
            {
              "slug": "chervona-ikra-4445",
              "children": [],
              "total": 30
            }
          ],
          "total": 61
        },
        {
          "slug": "moreprodukty-ta-moliusky-4435",
          "children": [
            {
              "slug": "zamorozheni-moreprodukty-ta-moliusky-4451",
              "children": [],
              "total": 66
            },
            {
              "slug": "okholodzheni-moreprodukty-ta-moliusky-4450",
              "children": [],
              "total": 36
            }
          ],
          "total": 102
        },
        {
          "slug": "krabovi-palychky-4438",
          "children": [],
          "total": 5
        },
        {
          "slug": "rybni-napivfabrykaty-4434",
          "children": [],
          "total": 5
        },
        {
          "slug": "ustrytsi-ta-lobstery-4436",
          "children": [],
          "total": 12
        },
        {
          "slug": "zamorozheni-ravlyky-4440",
          "children": [],
          "total": 8
        }
      ],
      "total": 364
    },
    {
      "slug": "kovbasni-vyroby-i-m-iasni-delikatesy-4731",
      "children": [
        {
          "slug": "sosysky-i-sardelky-4732",
          "children": [
            {
              "slug": "sosysky-4733",
              "children": [],
              "total": 42
            },
            {
              "slug": "sardelky-4734",
              "children": [],
              "total": 6
            }
          ],
          "total": 48
        },
        {
          "slug": "kovbasy-4735",
          "children": [
            {
              "slug": "varena-kovbasa-4736",
              "children": [],
              "total": 31
            },
            {
              "slug": "kopchena-kovbasa-4737",
              "children": [],
              "total": 35
            },
            {
              "slug": "syrov-ialena-syrokopchena-kovbasa-4738",
              "children": [],
              "total": 64
            },
            {
              "slug": "zapechena-kovbasa-4739",
              "children": [],
              "total": 8
            },
            {
              "slug": "krov-ianka-i-liverna-kovbasa-4740",
              "children": [],
              "total": 2
            },
            {
              "slug": "kovbasky-4741",
              "children": [],
              "total": 39
            }
          ],
          "total": 179
        },
        {
          "slug": "m-iasni-delikatesy-4742",
          "children": [
            {
              "slug": "balyk-4743",
              "children": [],
              "total": 22
            },
            {
              "slug": "buzhenyna-4744",
              "children": [],
              "total": 3
            },
            {
              "slug": "shynka-4745",
              "children": [],
              "total": 12
            },
            {
              "slug": "grudynka-i-bekon-4746",
              "children": [],
              "total": 21
            },
            {
              "slug": "m-iasni-rulety-4747",
              "children": [],
              "total": 7
            },
            {
              "slug": "okist-4748",
              "children": [],
              "total": 27
            },
            {
              "slug": "shyika-kopchena-4749",
              "children": [],
              "total": 8
            },
            {
              "slug": "basturma-4750",
              "children": [],
              "total": 7
            },
            {
              "slug": "pashtety-ta-namazky-4751",
              "children": [],
              "total": 32
            },
            {
              "slug": "kopchenosti-4752",
              "children": [],
              "total": 42
            },
            {
              "slug": "zelts-saltyson-iazyk-4753",
              "children": [],
              "total": 4
            },
            {
              "slug": "porosia-zapechene-4754",
              "children": []
            },
            {
              "slug": "m-iaso-dychyny-4755",
              "children": [],
              "total": 6
            }
          ],
          "total": 190
        },
        {
          "slug": "khamon-4756",
          "children": [],
          "total": 58
        },
        {
          "slug": "salo-4757",
          "children": [],
          "total": 15
        },
        {
          "slug": "m-iasni-sneky-4758",
          "children": [],
          "total": 23
        },
        {
          "slug": "m-iaso-kovbasna-narizka-4759",
          "children": [],
          "total": 17
        },
        {
          "slug": "vegan-4760",
          "children": [],
          "total": 9
        }
      ],
      "total": 472
    },
    {
      "slug": "syry-1468",
      "children": [
        {
          "slug": "syry-z-plisniavoiu-5002",
          "children": [],
          "total": 105
        },
        {
          "slug": "syry-rozsilni-feta-motsarela-inshi-5006",
          "children": [],
          "total": 108
        },
        {
          "slug": "tverdi-i-napivtverdi-syry-5008",
          "children": [
            {
              "slug": "vytrymani-parmezan-gauda-chedder-inshi-5011",
              "children": [],
              "total": 96
            },
            {
              "slug": "krupnoporysti-maasdam-radamer-inshi-5012",
              "children": [],
              "total": 12
            },
            {
              "slug": "napivtverdi-tenero-vershkovyi-inshi-5013",
              "children": [],
              "total": 19
            },
            {
              "slug": "syry-spetsialitety-5014",
              "children": [],
              "total": 114
            }
          ],
          "total": 241
        },
        {
          "slug": "koziachi-i-ovechi-syry-5010",
          "children": [],
          "total": 26
        },
        {
          "slug": "krem-syry-5005",
          "children": [],
          "total": 76
        },
        {
          "slug": "syry-plavleni-5007",
          "children": [],
          "total": 10
        },
        {
          "slug": "syry-dlia-ditei-5009",
          "children": [],
          "total": 1
        },
        {
          "slug": "nabory-syriv-1470",
          "children": [],
          "total": 6
        },
        {
          "slug": "sousy-do-syriv-4728",
          "children": [],
          "total": 23
        }
      ],
      "total": 569
    },
    {
      "slug": "khlib-ta-vypichka-5121",
      "children": [
        {
          "slug": "vlasna-vypichka-silpo-5194",
          "children": [
            {
              "slug": "khlib-i-bagety-vlasnoi-pekarni-5195",
              "children": [],
              "total": 32
            },
            {
              "slug": "bulochky-i-zdoba-vlasnoi-pekarni-5196",
              "children": [],
              "total": 21
            },
            {
              "slug": "pyrogy-i-syrnyky-vlasnoi-pekarni-5197",
              "children": [],
              "total": 6
            },
            {
              "slug": "donaty-i-pampukhy-vlasnoi-pekarni-5198",
              "children": [],
              "total": 2
            },
            {
              "slug": "sendvichi-vlasnoi-pekarni-5199",
              "children": [],
              "total": 2
            },
            {
              "slug": "kruasany-i-lystkovi-vyroby-vlasnoi-pekarni-5200",
              "children": [],
              "total": 8
            }
          ],
          "total": 71
        },
        {
          "slug": "khlibobulochni-vyroby-5122",
          "children": [
            {
              "slug": "khlib-5139",
              "children": [],
              "total": 65
            },
            {
              "slug": "baget-5143",
              "children": [],
              "total": 8
            },
            {
              "slug": "baton-5140",
              "children": [],
              "total": 4
            },
            {
              "slug": "chiabata-5142",
              "children": []
            },
            {
              "slug": "bulky-5144",
              "children": [],
              "total": 15
            },
            {
              "slug": "lavash-tortylia-5145",
              "children": [],
              "total": 12
            }
          ],
          "total": 104
        },
        {
          "slug": "vypichka-5138",
          "children": [
            {
              "slug": "bulochky-i-pyrizhky-5146",
              "children": [],
              "total": 17
            },
            {
              "slug": "pampukhy-donaty-churrosy-5147",
              "children": [],
              "total": 3
            },
            {
              "slug": "kruasany-5148",
              "children": [],
              "total": 21
            },
            {
              "slug": "vypichka-z-lystkovogo-tista-5149",
              "children": [],
              "total": 4
            },
            {
              "slug": "zdobna-vypichka-5150",
              "children": [],
              "total": 3
            },
            {
              "slug": "shtrudli-5151",
              "children": [],
              "total": 2
            },
            {
              "slug": "pyrogy-i-tarty-5152",
              "children": [],
              "total": 6
            },
            {
              "slug": "keksy-i-mafiny-5153",
              "children": [],
              "total": 13
            },
            {
              "slug": "sendvichi-pitsa-fokachcha-5154",
              "children": []
            },
            {
              "slug": "syrnyky-5155",
              "children": [],
              "total": 2
            },
            {
              "slug": "sviatkova-vypichka-5156",
              "children": [],
              "total": 1
            }
          ],
          "total": 72
        },
        {
          "slug": "korzhi-osnova-dlia-pitsy-5136",
          "children": [
            {
              "slug": "osnovy-dlia-pitsy-5157",
              "children": [],
              "total": 1
            },
            {
              "slug": "koshyky-ta-tartaletky-5158",
              "children": [],
              "total": 4
            },
            {
              "slug": "korzhi-dlia-tortiv-5160",
              "children": [],
              "total": 1
            },
            {
              "slug": "korzhi-vafelni-5159",
              "children": [],
              "total": 1
            }
          ],
          "total": 6
        },
        {
          "slug": "sushka-khlibtsi-prianyky-5137",
          "children": [
            {
              "slug": "sushka-5161",
              "children": [],
              "total": 4
            },
            {
              "slug": "sukhari-5162",
              "children": [],
              "total": 2
            },
            {
              "slug": "grinky-i-tosty-5163",
              "children": [],
              "total": 2
            },
            {
              "slug": "solomka-5164",
              "children": [],
              "total": 3
            },
            {
              "slug": "grissini-ta-khlibni-palychky-5165",
              "children": [],
              "total": 7
            },
            {
              "slug": "khlibtsi-5166",
              "children": [],
              "total": 13
            },
            {
              "slug": "prianyky-5167",
              "children": [],
              "total": 2
            }
          ],
          "total": 33
        }
      ],
      "total": 221
    },
    {
      "slug": "gotovi-stravy-i-kulinariia-4761",
      "children": [
        {
          "slug": "mlyntsi-syrnyky-zapikanky-4762",
          "children": [
            {
              "slug": "mlyntsi-4763",
              "children": [],
              "total": 11
            },
            {
              "slug": "syrnyky-i-zapikanky-4764",
              "children": [],
              "total": 14
            }
          ],
          "total": 25
        },
        {
          "slug": "pershi-stravy-4765",
          "children": [],
          "total": 12
        },
        {
          "slug": "drugi-stravy-4766",
          "children": [
            {
              "slug": "m-iasni-stravy-4767",
              "children": [],
              "total": 26
            },
            {
              "slug": "rybni-stravy-4768",
              "children": [],
              "total": 13
            },
            {
              "slug": "garniry-4769",
              "children": [],
              "total": 27
            },
            {
              "slug": "gryl-4770",
              "children": [],
              "total": 10
            },
            {
              "slug": "varenyky-pelmeni-giozy-khinkali-4771",
              "children": [],
              "total": 2
            }
          ],
          "total": 74
        },
        {
          "slug": "sushi-pitsa-burgery-4773",
          "children": [
            {
              "slug": "sushi-4774",
              "children": [],
              "total": 27
            },
            {
              "slug": "pitsa-4775",
              "children": [],
              "total": 12
            },
            {
              "slug": "burgery-i-sendvichi-4776",
              "children": [],
              "total": 6
            }
          ],
          "total": 45
        },
        {
          "slug": "salaty-ta-zakusky-4777",
          "children": [
            {
              "slug": "zakusky-ta-namazky-4778",
              "children": [],
              "total": 2
            },
            {
              "slug": "salaty-4779",
              "children": [],
              "total": 31
            },
            {
              "slug": "sousy-portsiini-4780",
              "children": [],
              "total": 2
            },
            {
              "slug": "marynovani-stravy-4781",
              "children": [],
              "total": 24
            }
          ],
          "total": 59
        },
        {
          "slug": "deserty-ta-napoi-4782",
          "children": [
            {
              "slug": "deserty-4786",
              "children": [],
              "total": 6
            },
            {
              "slug": "gotovi-napoi-4787",
              "children": [],
              "total": 4
            }
          ],
          "total": 10
        },
        {
          "slug": "snidanky-ta-kompleksni-obidy-4783",
          "children": [],
          "total": 4
        },
        {
          "slug": "pyrogy-pyrizhky-vypichka-4784",
          "children": [],
          "total": 14
        },
        {
          "slug": "napivfabrykaty-vlasnogo-vyrobnytstva-4785",
          "children": [],
          "total": 9
        },
        {
          "slug": "zhuistyka-silpo-5385",
          "children": [],
          "total": 1
        }
      ],
      "total": 252
    },
    {
      "slug": "molochni-produkty-ta-iaitsia-234",
      "children": [
        {
          "slug": "yaitsia-528",
          "children": [
            {
              "slug": "kuriachi-iaitsia-4977",
              "children": [],
              "total": 16
            },
            {
              "slug": "perepelyni-iaitsia-4978",
              "children": [],
              "total": 3
            },
            {
              "slug": "yaitsia-inshykh-ptakhiv-4979",
              "children": [],
              "total": 1
            }
          ],
          "total": 20
        },
        {
          "slug": "moloko-vershky-237",
          "children": [
            {
              "slug": "moloko-253",
              "children": [],
              "total": 65
            },
            {
              "slug": "vershky-257",
              "children": [],
              "total": 22
            },
            {
              "slug": "moloko-sukhe-256",
              "children": [],
              "total": 1
            }
          ],
          "total": 88
        },
        {
          "slug": "maslo-margaryn-spred-239",
          "children": [
            {
              "slug": "maslo-4980",
              "children": [],
              "total": 57
            },
            {
              "slug": "margaryn-4981",
              "children": []
            },
            {
              "slug": "spred-4982",
              "children": [],
              "total": 3
            }
          ],
          "total": 60
        },
        {
          "slug": "kyslomolochni-napoi-4983",
          "children": [
            {
              "slug": "kefir-riazhanka-airan-4984",
              "children": [],
              "total": 42
            },
            {
              "slug": "napoi-na-syrovattsi-4985",
              "children": [],
              "total": 2
            },
            {
              "slug": "zakvaska-4986",
              "children": [],
              "total": 1
            }
          ],
          "total": 45
        },
        {
          "slug": "syr-kyslomolochnyi-syrok-4987",
          "children": [
            {
              "slug": "syr-kyslomolochnyi-4988",
              "children": [],
              "total": 31
            },
            {
              "slug": "syrkova-masa-4989",
              "children": [],
              "total": 7
            }
          ],
          "total": 38
        },
        {
          "slug": "smetana-4376",
          "children": [],
          "total": 19
        },
        {
          "slug": "yogurty-deserty-235",
          "children": [
            {
              "slug": "biskvity-molochni-241",
              "children": [],
              "total": 5
            },
            {
              "slug": "yogurty-245",
              "children": [],
              "total": 156
            },
            {
              "slug": "molochni-i-syrkovi-deserty-4990",
              "children": [],
              "total": 26
            },
            {
              "slug": "molochni-pudyngy-i-zhele-4991",
              "children": [],
              "total": 19
            }
          ],
          "total": 207
        },
        {
          "slug": "glazurovani-syrky-4992",
          "children": [],
          "total": 25
        },
        {
          "slug": "zghushchene-moloko-4993",
          "children": [],
          "total": 12
        },
        {
          "slug": "molochni-produkty-dlia-ditei-4994",
          "children": [
            {
              "slug": "moloko-dlia-ditei-4995",
              "children": [],
              "total": 2
            },
            {
              "slug": "kyslomolochni-napoi-dlia-ditei-4996",
              "children": [],
              "total": 2
            },
            {
              "slug": "yogurty-dytiachi-4997",
              "children": [],
              "total": 14
            },
            {
              "slug": "syrky-dytiachi-4998",
              "children": []
            },
            {
              "slug": "molochni-deserty-dytiachi-4999",
              "children": []
            }
          ],
          "total": 18
        },
        {
          "slug": "bezlaktozna-molochna-produktsiia-5000",
          "children": [],
          "total": 50
        },
        {
          "slug": "bezmolochna-produktsiia-240",
          "children": [],
          "total": 54
        }
      ],
      "total": 598
    },
    {
      "slug": "vlasni-marky-5202",
      "children": [
        {
          "slug": "silpovi-khity-vlasnykh-marok-5203",
          "children": [],
          "total": 34
        },
        {
          "slug": "novynky-vlasnykh-marok-5204",
          "children": [],
          "total": 18
        },
        {
          "slug": "produkty-vlasnykh-marok-5205",
          "children": [],
          "total": 166
        },
        {
          "slug": "dlia-kukhni-vid-vlasnykh-marok-5206",
          "children": [],
          "total": 29
        },
        {
          "slug": "dlia-domu-i-krasy-vid-vlasnykh-marok-5207",
          "children": [],
          "total": 41
        },
        {
          "slug": "napoi-vlasnykh-marok-5208",
          "children": [],
          "total": 27
        }
      ],
      "total": 263
    },
    {
      "slug": "lavka-tradytsii-4487",
      "children": [
        {
          "slug": "fermerske-moloko-iogurty-syry-4488",
          "children": [
            {
              "slug": "fermerske-moloko-ta-vershky-5496",
              "children": [],
              "total": 18
            },
            {
              "slug": "fermerski-kyslomolochni-napoi-5494",
              "children": [],
              "total": 19
            },
            {
              "slug": "fermerski-iogurty-5493",
              "children": [],
              "total": 57
            },
            {
              "slug": "fermerska-smetana-5499",
              "children": [],
              "total": 10
            },
            {
              "slug": "kraftovyi-kyslomolochnyi-syr-5497",
              "children": [],
              "total": 15
            },
            {
              "slug": "maslo-z-fermerskykh-vershkiv-5495",
              "children": [],
              "total": 20
            },
            {
              "slug": "deserty-i-zapikanky-5491",
              "children": [],
              "total": 16
            },
            {
              "slug": "fermerske-zghushchene-moloko-5492",
              "children": [],
              "total": 7
            },
            {
              "slug": "syrky-glazurovani-5498",
              "children": [],
              "total": 19
            }
          ],
          "total": 181
        },
        {
          "slug": "fermerski-iaitsia-5500",
          "children": [],
          "total": 3
        },
        {
          "slug": "kraftove-m-iaso-i-kovbasa-4489",
          "children": [
            {
              "slug": "vareni-kovbasni-vyroby-5468",
              "children": [],
              "total": 28
            },
            {
              "slug": "fermerski-kovbasy-5469",
              "children": [],
              "total": 52
            },
            {
              "slug": "fermerski-m-iasni-delikatesy-5470",
              "children": [],
              "total": 66
            },
            {
              "slug": "fermerski-m-iasni-sneky-5473",
              "children": [],
              "total": 16
            },
            {
              "slug": "fermerske-salo-5472",
              "children": [],
              "total": 15
            }
          ],
          "total": 177
        },
        {
          "slug": "kraftovi-syry-5474",
          "children": [
            {
              "slug": "kraftovi-syry-z-plisniavoiu-5475",
              "children": [],
              "total": 15
            },
            {
              "slug": "syry-m-iaki-5476",
              "children": [],
              "total": 66
            },
            {
              "slug": "syry-rozsolni-5477",
              "children": [],
              "total": 21
            },
            {
              "slug": "syry-tverdi-i-napivtverdi-5478",
              "children": [],
              "total": 60
            }
          ],
          "total": 162
        },
        {
          "slug": "fermerska-zamorozhena-produktsiia-5463",
          "children": [
            {
              "slug": "zamorozka-ruchnoi-lipky-4490",
              "children": [],
              "total": 42
            },
            {
              "slug": "m-iasni-i-ovochevi-napivfabrykaty-5464",
              "children": [],
              "total": 2
            },
            {
              "slug": "ravlyky-5465",
              "children": [],
              "total": 8
            }
          ],
          "total": 52
        },
        {
          "slug": "bakaliia-sousy-i-med-4491",
          "children": [
            {
              "slug": "bakaliia-5449",
              "children": [],
              "total": 22
            },
            {
              "slug": "domashnia-konservatsiia-5450",
              "children": [],
              "total": 97
            },
            {
              "slug": "prypravy-ta-prianoshchi-5451",
              "children": [],
              "total": 55
            }
          ],
          "total": 174
        },
        {
          "slug": "kraftove-morozyvo-i-deserty-5466",
          "children": [
            {
              "slug": "kraftove-morozyvo-4497",
              "children": [],
              "total": 17
            },
            {
              "slug": "deserty-zamorozheni-5467",
              "children": [],
              "total": 21
            }
          ],
          "total": 38
        },
        {
          "slug": "sneky-lavka-tradytsii-4492",
          "children": [
            {
              "slug": "naturalni-chypsy-5486",
              "children": [],
              "total": 13
            },
            {
              "slug": "gotovi-snidanky-i-krekery-5482",
              "children": [],
              "total": 19
            },
            {
              "slug": "sublimovani-frukty-ta-ovochi-5483",
              "children": [],
              "total": 9
            },
            {
              "slug": "naturalni-sukhofrukty-ta-tsukaty-5484",
              "children": [],
              "total": 12
            },
            {
              "slug": "khlibtsi-zernovi-5485",
              "children": [],
              "total": 20
            }
          ],
          "total": 73
        },
        {
          "slug": "trav-iani-zbory-kakao-4493",
          "children": [],
          "total": 50
        },
        {
          "slug": "vypichka-i-solodoshchi-4494",
          "children": [
            {
              "slug": "naturalnyi-shokolad-5490",
              "children": [],
              "total": 43
            },
            {
              "slug": "kraftovi-tsukerky-5489",
              "children": [],
              "total": 13
            },
            {
              "slug": "prianyky-ta-pechyvo-5487",
              "children": [],
              "total": 7
            },
            {
              "slug": "fruktovi-lasoshchi-ta-drazhe-5488",
              "children": [],
              "total": 20
            }
          ],
          "total": 83
        },
        {
          "slug": "napoi-i-soky-4495",
          "children": [
            {
              "slug": "soky-fermerskogo-vyrobnytstva-5479",
              "children": [],
              "total": 43
            },
            {
              "slug": "nektary-fermerskogo-vyrobnytstva-5481",
              "children": [],
              "total": 3
            },
            {
              "slug": "fermentovani-napoi-5480",
              "children": [],
              "total": 16
            }
          ],
          "total": 62
        },
        {
          "slug": "avtorski-alkogolni-napoi-4496",
          "children": [
            {
              "slug": "mitsni-napoi-5446",
              "children": [],
              "total": 11
            },
            {
              "slug": "sydr-5447",
              "children": [],
              "total": 22
            },
            {
              "slug": "med-pytnyi-5448",
              "children": []
            }
          ],
          "total": 33
        },
        {
          "slug": "dekor-dlia-domu-4498",
          "children": [
            {
              "slug": "aromaty-ta-osvizhuvachi-dlia-domu-5452",
              "children": [],
              "total": 7
            },
            {
              "slug": "roslynna-kosmetyka-5454",
              "children": [],
              "total": 7
            },
            {
              "slug": "vazy-5455",
              "children": [],
              "total": 2
            },
            {
              "slug": "tekstyl-dlia-domu-5456",
              "children": []
            },
            {
              "slug": "zberigannia-izhi-5457",
              "children": []
            },
            {
              "slug": "posud-ta-kukhonne-pryladdia-5458",
              "children": [],
              "total": 8
            },
            {
              "slug": "svichky-pidsvichnyky-5459",
              "children": [],
              "total": 35
            },
            {
              "slug": "suveniry-5460",
              "children": [],
              "total": 14
            },
            {
              "slug": "sumky-5461",
              "children": []
            },
            {
              "slug": "dlia-ditei-5462",
              "children": []
            }
          ],
          "total": 73
        }
      ],
      "total": 1161
    },
    {
      "slug": "aptechka-zdorov-ia-5263",
      "children": [
        {
          "slug": "tovary-medychnogo-pryznachennia-5264",
          "children": [
            {
              "slug": "perev-iazuvalni-materialy-5272",
              "children": []
            },
            {
              "slug": "leikoplastyri-5273",
              "children": []
            },
            {
              "slug": "diagnostychni-testy-5274",
              "children": []
            },
            {
              "slug": "odnorazovyi-odiag-5275",
              "children": []
            },
            {
              "slug": "manipuliatsiini-zasoby-5276",
              "children": []
            },
            {
              "slug": "dlia-analiziv-i-laboratorii-5277",
              "children": []
            },
            {
              "slug": "medychni-vyroby-5278",
              "children": []
            },
            {
              "slug": "ortopediia-i-reabilitatsiia-5279",
              "children": []
            },
            {
              "slug": "medtekhnika-5280",
              "children": []
            },
            {
              "slug": "tovary-dlia-snu-5281",
              "children": []
            }
          ]
        },
        {
          "slug": "tovary-dlia-ditei-5265",
          "children": [
            {
              "slug": "dytiacha-gigiiena-i-dogliad-5282",
              "children": []
            },
            {
              "slug": "servetky-pidguzky-5283",
              "children": []
            },
            {
              "slug": "kosmetyka-dlia-ditei-5284",
              "children": []
            },
            {
              "slug": "dytiachi-sumishi-5285",
              "children": []
            },
            {
              "slug": "kharchuvannia-dlia-ditei-5286",
              "children": []
            },
            {
              "slug": "dlia-goduvannia-5287",
              "children": []
            },
            {
              "slug": "pustushky-5288",
              "children": []
            },
            {
              "slug": "igrashky-i-prorizuvachi-5289",
              "children": []
            },
            {
              "slug": "dytiachi-serezhky-i-aksesuary-5290",
              "children": []
            },
            {
              "slug": "dlia-vagitnykh-i-mam-5291",
              "children": []
            }
          ]
        },
        {
          "slug": "osobysta-gigiiena-5266",
          "children": [
            {
              "slug": "dogliad-za-rotovoiu-porozhnynoiu-5292",
              "children": []
            },
            {
              "slug": "prokladky-i-tampony-5293",
              "children": []
            },
            {
              "slug": "pidguzky-dlia-doroslykh-5294",
              "children": []
            },
            {
              "slug": "peliushky-5295",
              "children": []
            },
            {
              "slug": "paperovi-i-vatni-vyroby-5296",
              "children": []
            },
            {
              "slug": "intymni-tovary-5297",
              "children": []
            }
          ]
        },
        {
          "slug": "liky-za-diieiu-5267",
          "children": [
            {
              "slug": "antybiotyky-5298",
              "children": []
            },
            {
              "slug": "antygistaminni-5299",
              "children": []
            },
            {
              "slug": "vid-zastudy-i-grypu-5300",
              "children": []
            },
            {
              "slug": "vitaminy-5301",
              "children": []
            },
            {
              "slug": "zneboliuvalni-5302",
              "children": []
            },
            {
              "slug": "dermatologiia-5303",
              "children": []
            },
            {
              "slug": "gormonalni-preparaty-5304",
              "children": []
            },
            {
              "slug": "protyparazytarni-preparaty-5305",
              "children": []
            },
            {
              "slug": "profilaktychni-zasoby-5306",
              "children": []
            },
            {
              "slug": "rozchyny-i-diagnostychni-preparaty-5307",
              "children": []
            }
          ]
        },
        {
          "slug": "liky-za-systemamy-organizmu-5268",
          "children": [
            {
              "slug": "dlia-sertsevo-sudynnoi-systemy-5308",
              "children": []
            },
            {
              "slug": "dlia-nervovoi-systemy-5309",
              "children": []
            },
            {
              "slug": "dlia-travnogo-traktu-5310",
              "children": []
            },
            {
              "slug": "dlia-kistkovo-m-iazovoi-systemy-5311",
              "children": []
            },
            {
              "slug": "dlia-sechostatevoi-systemy-5312",
              "children": []
            },
            {
              "slug": "dlia-krovotvorennia-i-krovi-5313",
              "children": []
            },
            {
              "slug": "dlia-porozhnyny-rota-5314",
              "children": []
            },
            {
              "slug": "dlia-ochei-i-vukh-5315",
              "children": []
            }
          ]
        },
        {
          "slug": "vitaminy-i-dobavky-5269",
          "children": [
            {
              "slug": "vitaminy-i-kompleksy-5316",
              "children": []
            },
            {
              "slug": "dobavky-dlia-imunitetu-5317",
              "children": []
            },
            {
              "slug": "dobavky-dlia-sertsia-sudyn-nerviv-5318",
              "children": []
            },
            {
              "slug": "dobavky-dlia-m-iaziv-i-suglobiv-5319",
              "children": []
            },
            {
              "slug": "dobavky-dlia-nyrok-i-sechostatevoi-systemy-5320",
              "children": []
            },
            {
              "slug": "dobavky-dlia-reproduktyvnoi-systemy-5321",
              "children": []
            },
            {
              "slug": "dobavky-dlia-shchytovydnoi-zalozy-5322",
              "children": []
            },
            {
              "slug": "dobavky-dlia-organiv-dykhannia-5323",
              "children": []
            },
            {
              "slug": "dobavky-dlia-organiv-zoru-5324",
              "children": []
            },
            {
              "slug": "dobavky-dlia-shkiry-nigtiv-i-volossia-5325",
              "children": []
            },
            {
              "slug": "dobavky-dlia-shkt-i-pechinky-5326",
              "children": []
            },
            {
              "slug": "dobavky-dlia-diabetykiv-5327",
              "children": []
            },
            {
              "slug": "sportyvne-i-diietychne-kharchuvannia-5328",
              "children": []
            }
          ]
        },
        {
          "slug": "krasa-i-dogliad-5270",
          "children": [
            {
              "slug": "zasoby-dlia-volossia-5329",
              "children": []
            },
            {
              "slug": "balzamy-kondytsionery-shampuni-5330",
              "children": []
            },
            {
              "slug": "zasoby-dogliadu-za-tilom-5331",
              "children": []
            },
            {
              "slug": "zasoby-dlia-dushu-5332",
              "children": []
            },
            {
              "slug": "dezodoranty-5333",
              "children": []
            },
            {
              "slug": "zasoby-dlia-oblychchia-5334",
              "children": []
            },
            {
              "slug": "zasoby-dlia-gub-5335",
              "children": []
            },
            {
              "slug": "zasoby-dlia-ochei-5336",
              "children": []
            },
            {
              "slug": "dogliad-za-rukamy-i-nogamy-5337",
              "children": []
            },
            {
              "slug": "sontsezakhyst-5338",
              "children": []
            },
            {
              "slug": "zasoby-vid-komakh-5339",
              "children": []
            },
            {
              "slug": "podarunkovi-nabory-5340",
              "children": []
            },
            {
              "slug": "aromaterapiia-5341",
              "children": []
            }
          ]
        },
        {
          "slug": "dermatokosmetyka-5271",
          "children": [
            {
              "slug": "vid-akne-5342",
              "children": []
            },
            {
              "slug": "vid-lupy-5343",
              "children": []
            },
            {
              "slug": "pry-vypadinni-volossia-5344",
              "children": []
            },
            {
              "slug": "vid-seboreinogo-dermatytu-5345",
              "children": []
            },
            {
              "slug": "pry-demodekozi-5346",
              "children": []
            },
            {
              "slug": "pry-psoriazi-5348",
              "children": []
            },
            {
              "slug": "pry-atopichnomu-dermatyti-5349",
              "children": []
            },
            {
              "slug": "vid-kuperozu-5350",
              "children": []
            }
          ]
        }
      ]
    },
    {
      "slug": "bady-5222",
      "children": [
        {
          "slug": "vitaminy-i-mineraly-5223",
          "children": [
            {
              "slug": "vitaminy-5231",
              "children": [],
              "total": 21
            },
            {
              "slug": "mineraly-5232",
              "children": [],
              "total": 19
            },
            {
              "slug": "kompleksy-vitaminiv-i-mineraliv-5233",
              "children": [],
              "total": 13
            },
            {
              "slug": "vitaminy-dlia-imunitetu-5234",
              "children": [],
              "total": 4
            },
            {
              "slug": "omega-5235",
              "children": [],
              "total": 11
            },
            {
              "slug": "multyvitaminy-5236",
              "children": [],
              "total": 9
            }
          ],
          "total": 77
        },
        {
          "slug": "detoks-i-bady-dlia-travlennia-5224",
          "children": [
            {
              "slug": "fermenty-5237",
              "children": [],
              "total": 18
            },
            {
              "slug": "sorbenty-5238",
              "children": [],
              "total": 7
            },
            {
              "slug": "dlia-detoksu-i-pidtrymky-pechinky-5239",
              "children": [],
              "total": 20
            },
            {
              "slug": "pre-i-probiotyky-5240",
              "children": [],
              "total": 4
            },
            {
              "slug": "klitkovyna-5241",
              "children": []
            }
          ],
          "total": 49
        },
        {
          "slug": "antystres-i-bady-dlia-snu-5225",
          "children": [
            {
              "slug": "bady-vid-stresu-5242",
              "children": [],
              "total": 4
            },
            {
              "slug": "melatonin-i-kompleksy-dlia-snu-5243",
              "children": [],
              "total": 4
            },
            {
              "slug": "magnii-5244",
              "children": [],
              "total": 9
            }
          ],
          "total": 17
        },
        {
          "slug": "bady-dlia-krasy-5226",
          "children": [
            {
              "slug": "vitaminy-dlia-volossia-shkiry-nigtiv-5245",
              "children": [],
              "total": 12
            },
            {
              "slug": "kolagen-5246",
              "children": [],
              "total": 10
            }
          ],
          "total": 22
        },
        {
          "slug": "sportyvne-kharchuvannia-5227",
          "children": [
            {
              "slug": "proteinovi-batonchyky-5247",
              "children": [],
              "total": 14
            },
            {
              "slug": "aminokysloty-5248",
              "children": [],
              "total": 13
            },
            {
              "slug": "protein-5249",
              "children": [],
              "total": 8
            },
            {
              "slug": "dlia-kistok-i-suglobiv-5250",
              "children": [],
              "total": 6
            },
            {
              "slug": "peredtrenuvalni-kompleksy-5251",
              "children": [],
              "total": 3
            },
            {
              "slug": "geinery-5252",
              "children": [],
              "total": 1
            },
            {
              "slug": "sheikery-5253",
              "children": []
            }
          ],
          "total": 45
        },
        {
          "slug": "bady-dlia-pam-iati-sudyn-sertsia-5228",
          "children": [
            {
              "slug": "bady-dlia-sertsia-i-sudyn-5254",
              "children": [],
              "total": 8
            },
            {
              "slug": "adaptogeny-5255",
              "children": [],
              "total": 5
            },
            {
              "slug": "bady-dlia-energii-5256",
              "children": [],
              "total": 4
            },
            {
              "slug": "bady-dlia-pam-iati-ta-kontsentratsii-5257",
              "children": [],
              "total": 2
            }
          ],
          "total": 19
        },
        {
          "slug": "bady-dlia-vagitnykh-i-ditei-5229",
          "children": [
            {
              "slug": "vitaminy-dlia-vagitnykh-5258",
              "children": [],
              "total": 9
            },
            {
              "slug": "vitaminy-dlia-ditei-5259",
              "children": [],
              "total": 11
            }
          ],
          "total": 20
        },
        {
          "slug": "cbd-i-funktsionalni-gryby-5230",
          "children": [
            {
              "slug": "oliia-cbd-5260",
              "children": [],
              "total": 7
            },
            {
              "slug": "kapsuly-cbd-5261",
              "children": [],
              "total": 2
            },
            {
              "slug": "funktsionalni-gryby-5262",
              "children": [],
              "total": 9
            }
          ],
          "total": 18
        }
      ],
      "total": 267
    },
    {
      "slug": "zdorove-kharchuvannia-4864",
      "children": [
        {
          "slug": "organichna-izha-4865",
          "children": [],
          "total": 138
        },
        {
          "slug": "veganski-produkty-4866",
          "children": [],
          "total": 267
        },
        {
          "slug": "bezlaktozni-produkty-4867",
          "children": [],
          "total": 132
        },
        {
          "slug": "bezghliutenovi-produkty-4868",
          "children": [],
          "total": 173
        },
        {
          "slug": "bez-dodanogo-tsukru-4869",
          "children": [],
          "total": 173
        },
        {
          "slug": "diietychne-kharchuvannia-5001",
          "children": [],
          "total": 128
        }
      ],
      "total": 643
    },
    {
      "slug": "bakaliia-i-konservy-4870",
      "children": [
        {
          "slug": "krupy-4871",
          "children": [
            {
              "slug": "grechka-4872",
              "children": [],
              "total": 7
            },
            {
              "slug": "rys-4873",
              "children": [],
              "total": 46
            },
            {
              "slug": "pshenychna-krupa-4874",
              "children": [],
              "total": 5
            },
            {
              "slug": "bulgur-4875",
              "children": [],
              "total": 4
            },
            {
              "slug": "kuskus-4876",
              "children": [],
              "total": 9
            },
            {
              "slug": "vivsiana-krupa-4877",
              "children": [],
              "total": 18
            },
            {
              "slug": "superfudy-4878",
              "children": [],
              "total": 14
            },
            {
              "slug": "bobovi-4879",
              "children": [],
              "total": 11
            },
            {
              "slug": "inshi-krupy-4880",
              "children": [],
              "total": 12
            },
            {
              "slug": "kutia-4881",
              "children": []
            },
            {
              "slug": "soia-i-soievi-produkty-4882",
              "children": []
            }
          ],
          "total": 126
        },
        {
          "slug": "makaronni-vyroby-4883",
          "children": [
            {
              "slug": "makarony-4884",
              "children": [],
              "total": 69
            },
            {
              "slug": "aziiska-lokshyna-4885",
              "children": [],
              "total": 3
            },
            {
              "slug": "dlia-lazani-i-zapikannia-4886",
              "children": [],
              "total": 3
            },
            {
              "slug": "sousy-dlia-pasty-4887",
              "children": [],
              "total": 40
            }
          ],
          "total": 112
        },
        {
          "slug": "boroshno-4888",
          "children": [
            {
              "slug": "pshenychne-boroshno-4889",
              "children": [],
              "total": 15
            },
            {
              "slug": "z-tverdykh-sortiv-4890",
              "children": [],
              "total": 2
            },
            {
              "slug": "zhytnie-boroshno-4891",
              "children": [],
              "total": 2
            },
            {
              "slug": "grechane-boroshno-4892",
              "children": [],
              "total": 2
            },
            {
              "slug": "rysove-boroshno-4894",
              "children": [],
              "total": 1
            },
            {
              "slug": "vivsiane-boroshno-4893",
              "children": [],
              "total": 1
            },
            {
              "slug": "inshi-vydy-boroshna-4895",
              "children": [],
              "total": 21
            },
            {
              "slug": "tsilnozernove-boroshno-4896",
              "children": [],
              "total": 5
            },
            {
              "slug": "bezghliutenove-boroshno-4897",
              "children": [],
              "total": 7
            },
            {
              "slug": "sumishi-dlia-vypichky-4898",
              "children": [],
              "total": 9
            },
            {
              "slug": "solod-4899",
              "children": []
            },
            {
              "slug": "vysivky-5015",
              "children": [],
              "total": 3
            }
          ],
          "total": 56
        },
        {
          "slug": "sil-tsukor-4900",
          "children": [
            {
              "slug": "sil-4901",
              "children": [],
              "total": 62
            },
            {
              "slug": "tsukor-4902",
              "children": [],
              "total": 12
            },
            {
              "slug": "tsukrozaminnyky-4903",
              "children": [],
              "total": 1
            }
          ],
          "total": 75
        },
        {
          "slug": "oliia-ta-otset-4904",
          "children": [
            {
              "slug": "soniashnykova-oliia-4905",
              "children": [],
              "total": 7
            },
            {
              "slug": "olyvkova-oliia-4906",
              "children": [],
              "total": 118
            },
            {
              "slug": "inshi-olii-4907",
              "children": [],
              "total": 30
            },
            {
              "slug": "otset-4908",
              "children": [],
              "total": 55
            },
            {
              "slug": "sik-kontsentrat-4909",
              "children": [],
              "total": 2
            }
          ],
          "total": 212
        },
        {
          "slug": "konservatsiia-4910",
          "children": [
            {
              "slug": "m-iasna-4911",
              "children": [],
              "total": 26
            },
            {
              "slug": "rybna-4912",
              "children": [],
              "total": 87
            },
            {
              "slug": "ovocheva-4913",
              "children": [],
              "total": 35
            },
            {
              "slug": "goroshok-kukurudza-4914",
              "children": [],
              "total": 17
            },
            {
              "slug": "grybna-4915",
              "children": [],
              "total": 28
            },
            {
              "slug": "olyvky-4916",
              "children": [],
              "total": 77
            },
            {
              "slug": "kapersy-artyshoky-zakusky-4917",
              "children": [],
              "total": 43
            }
          ],
          "total": 313
        },
        {
          "slug": "konservovani-frukty-varennia-med-4918",
          "children": [
            {
              "slug": "fruktova-konservatsiia-4919",
              "children": [],
              "total": 20
            },
            {
              "slug": "pasty-shokoladno-gorikhovi-4920",
              "children": [],
              "total": 51
            },
            {
              "slug": "varennia-ta-dzhemy-4921",
              "children": [],
              "total": 90
            },
            {
              "slug": "med-4922",
              "children": [],
              "total": 44
            },
            {
              "slug": "syropy-i-topingy-4923",
              "children": [],
              "total": 17
            }
          ],
          "total": 222
        },
        {
          "slug": "yizha-shvydkogo-prygotuvannia-4924",
          "children": [
            {
              "slug": "plastivtsi-4925",
              "children": [],
              "total": 17
            },
            {
              "slug": "miusli-i-granola-4926",
              "children": [],
              "total": 48
            },
            {
              "slug": "gotovi-snidanky-4927",
              "children": [],
              "total": 44
            },
            {
              "slug": "kashi-4928",
              "children": [],
              "total": 3
            },
            {
              "slug": "lokshyna-4929",
              "children": [],
              "total": 4
            },
            {
              "slug": "supy-i-piure-4930",
              "children": [],
              "total": 4
            }
          ],
          "total": 120
        },
        {
          "slug": "aziiska-kukhnia-4931",
          "children": [
            {
              "slug": "sousy-prypravy-4932",
              "children": [],
              "total": 97
            },
            {
              "slug": "rys-ta-lokshyna-4934",
              "children": [],
              "total": 41
            },
            {
              "slug": "vodorosti-4935",
              "children": [],
              "total": 6
            },
            {
              "slug": "aziiski-stravy-shvydkogo-prygotuvannia-4936",
              "children": [],
              "total": 7
            },
            {
              "slug": "nabory-dlia-prygotuvannia-4937",
              "children": [],
              "total": 9
            }
          ],
          "total": 160
        }
      ],
      "total": 1380
    },
    {
      "slug": "sousy-i-spetsii-4938",
      "children": [
        {
          "slug": "sousy-zapravky-4939",
          "children": [
            {
              "slug": "ketchup-4948",
              "children": [],
              "total": 14
            },
            {
              "slug": "sousy-4949",
              "children": [],
              "total": 142
            },
            {
              "slug": "adzhyka-4950",
              "children": [],
              "total": 3
            },
            {
              "slug": "maionez-4951",
              "children": [],
              "total": 17
            },
            {
              "slug": "soievyi-sous-4976",
              "children": [],
              "total": 8
            },
            {
              "slug": "zapravky-4952",
              "children": []
            },
            {
              "slug": "marynady-4953",
              "children": [],
              "total": 8
            },
            {
              "slug": "tomatna-pasta-i-piure-4954",
              "children": [],
              "total": 12
            },
            {
              "slug": "girchytsia-4955",
              "children": [],
              "total": 20
            },
            {
              "slug": "khrin-4956",
              "children": [],
              "total": 7
            }
          ],
          "total": 231
        },
        {
          "slug": "spetsii-4941",
          "children": [
            {
              "slug": "perets-i-sumishi-pertsiv-4957",
              "children": [],
              "total": 35
            },
            {
              "slug": "lavrovyi-lyst-4958",
              "children": [],
              "total": 2
            },
            {
              "slug": "spetsii-i-travy-4959",
              "children": [],
              "total": 72
            },
            {
              "slug": "universalni-prypravy-4960",
              "children": [],
              "total": 56
            },
            {
              "slug": "susheni-ovochi-4961",
              "children": [],
              "total": 6
            },
            {
              "slug": "sil-zi-spetsiiamy-4962",
              "children": [],
              "total": 8
            },
            {
              "slug": "tsukor-zi-spetsiiamy-4963",
              "children": []
            }
          ],
          "total": 179
        },
        {
          "slug": "vse-dlia-vypichky-4942",
          "children": [
            {
              "slug": "aromatyzatory-4964",
              "children": [],
              "total": 14
            },
            {
              "slug": "soda-i-rozpushuvach-4965",
              "children": [],
              "total": 6
            },
            {
              "slug": "drizhdzhi-4966",
              "children": [],
              "total": 2
            },
            {
              "slug": "lymonna-kyslota-4967",
              "children": [],
              "total": 1
            },
            {
              "slug": "nachynky-i-posypky-4968",
              "children": [],
              "total": 36
            },
            {
              "slug": "tsukrova-pudra-4969",
              "children": [],
              "total": 4
            },
            {
              "slug": "kakao-poroshok-4970",
              "children": [],
              "total": 3
            },
            {
              "slug": "krem-dlia-vypichky-4971",
              "children": [],
              "total": 1
            },
            {
              "slug": "prypravy-do-vypichky-4972",
              "children": [],
              "total": 6
            },
            {
              "slug": "kysil-zhele-pudyngy-4973",
              "children": [],
              "total": 1
            },
            {
              "slug": "krokhmal-zagushchuvach-4974",
              "children": [],
              "total": 9
            },
            {
              "slug": "zagotovky-dlia-desertiv-4975",
              "children": [],
              "total": 12
            }
          ],
          "total": 94
        },
        {
          "slug": "paniruvannia-4943",
          "children": [],
          "total": 5
        }
      ],
      "total": 509
    },
    {
      "slug": "solodoshchi-498",
      "children": [
        {
          "slug": "vlasna-kondyterska-5044",
          "children": [
            {
              "slug": "torty-5045",
              "children": [],
              "total": 16
            },
            {
              "slug": "tistechka-5047",
              "children": [],
              "total": 59
            },
            {
              "slug": "keksy-i-rulety-5046",
              "children": [],
              "total": 3
            },
            {
              "slug": "shokolad-ruchnoi-roboty-5048",
              "children": [],
              "total": 15
            },
            {
              "slug": "tsukerky-ruchnoi-roboty-5049",
              "children": [],
              "total": 49
            },
            {
              "slug": "drazhe-5050",
              "children": [],
              "total": 9
            },
            {
              "slug": "shokoladni-figurky-5051",
              "children": [],
              "total": 5
            },
            {
              "slug": "marmelad-i-zefir-5052",
              "children": [],
              "total": 18
            },
            {
              "slug": "pechyvo-5053",
              "children": [],
              "total": 22
            }
          ],
          "total": 194
        },
        {
          "slug": "torty-tistechka-663",
          "children": [
            {
              "slug": "torty-5054",
              "children": [],
              "total": 15
            },
            {
              "slug": "tistechka-5055",
              "children": [],
              "total": 44
            }
          ],
          "total": 70
        },
        {
          "slug": "shokolad-505",
          "children": [
            {
              "slug": "shokoladni-figurky-524",
              "children": [],
              "total": 7
            },
            {
              "slug": "shokoladni-batonchyky-525",
              "children": [],
              "total": 40
            },
            {
              "slug": "shokolad-plytka-523",
              "children": [],
              "total": 244
            },
            {
              "slug": "shokoladni-iaitsia-526",
              "children": [],
              "total": 2
            }
          ],
          "total": 293
        },
        {
          "slug": "tsukerky-503",
          "children": [
            {
              "slug": "shokoladni-tsukerky-5056",
              "children": [],
              "total": 86
            },
            {
              "slug": "tsukerky-v-korobtsi-5057",
              "children": [],
              "total": 123
            },
            {
              "slug": "pomadni-tsukerky-i-irysky-5058",
              "children": [],
              "total": 2
            },
            {
              "slug": "sufle-i-ptashyne-moloko-5059",
              "children": [],
              "total": 5
            },
            {
              "slug": "frukty-v-shokoladi-5060",
              "children": [],
              "total": 4
            },
            {
              "slug": "drazhe-5061",
              "children": [],
              "total": 11
            },
            {
              "slug": "lodianyky-5062",
              "children": [],
              "total": 30
            },
            {
              "slug": "zheleini-tsukerky-5063",
              "children": [],
              "total": 91
            }
          ],
          "total": 347
        },
        {
          "slug": "pechyvo-vafli-biskvity-5064",
          "children": [
            {
              "slug": "pechyvo-5065",
              "children": [],
              "total": 124
            },
            {
              "slug": "vafli-5066",
              "children": [],
              "total": 34
            },
            {
              "slug": "biskvity-rulety-keksy-5067",
              "children": [],
              "total": 13
            },
            {
              "slug": "krekery-5068",
              "children": [],
              "total": 20
            }
          ],
          "total": 191
        },
        {
          "slug": "zefir-marmelad-pastyla-504",
          "children": [
            {
              "slug": "zefir-5069",
              "children": [],
              "total": 12
            },
            {
              "slug": "marshmelou-5070",
              "children": [],
              "total": 3
            },
            {
              "slug": "marmelad-5071",
              "children": [],
              "total": 16
            },
            {
              "slug": "pastyla-5072",
              "children": [],
              "total": 13
            },
            {
              "slug": "solodka-vata-5073",
              "children": []
            }
          ],
          "total": 43
        },
        {
          "slug": "skhidni-solodoshchi-502",
          "children": [
            {
              "slug": "gorikhy-v-syropi-517",
              "children": [],
              "total": 17
            },
            {
              "slug": "kozynaky-513",
              "children": []
            },
            {
              "slug": "lukum-514",
              "children": [],
              "total": 11
            },
            {
              "slug": "nuga-515",
              "children": [],
              "total": 3
            },
            {
              "slug": "pakhlava-519",
              "children": [],
              "total": 1
            },
            {
              "slug": "khalva-516",
              "children": [],
              "total": 9
            },
            {
              "slug": "sherbet-518",
              "children": [],
              "total": 1
            },
            {
              "slug": "pishmaniie-5074",
              "children": []
            }
          ],
          "total": 41
        },
        {
          "slug": "zhuvalna-gumka-5075",
          "children": [],
          "total": 19
        },
        {
          "slug": "solodoshchi-bez-dodanogo-tsukru-5076",
          "children": [
            {
              "slug": "tsukerky-shokolad-batonchyky-5077",
              "children": [],
              "total": 32
            },
            {
              "slug": "pechyvo-vafli-5078",
              "children": [],
              "total": 13
            },
            {
              "slug": "pastyla-zefir-marmelad-5079",
              "children": [],
              "total": 2
            },
            {
              "slug": "skhidni-solodoshchi-5080",
              "children": [],
              "total": 6
            }
          ],
          "total": 53
        },
        {
          "slug": "solodoshchi-do-sviat-5081",
          "children": [
            {
              "slug": "solodki-podarunky-dlia-ditei-5083",
              "children": [],
              "total": 1
            },
            {
              "slug": "shokoladni-figurky-sviatkovi-5084",
              "children": [],
              "total": 2
            },
            {
              "slug": "podarunkovi-tsukerky-5085",
              "children": [],
              "total": 4
            },
            {
              "slug": "panetone-sviatkovi-keksy-5082",
              "children": []
            },
            {
              "slug": "podarunkove-pechyvo-i-prianyky-5086",
              "children": [],
              "total": 7
            }
          ],
          "total": 13
        }
      ],
      "total": 1131
    },
    {
      "slug": "sneky-ta-chypsy-5016",
      "children": [
        {
          "slug": "chypsy-5017",
          "children": [
            {
              "slug": "chypsy-z-nori-5018",
              "children": [],
              "total": 9
            },
            {
              "slug": "fruktovi-chypsy-5019",
              "children": [],
              "total": 22
            },
            {
              "slug": "ovochevi-chypsy-5020",
              "children": [],
              "total": 16
            },
            {
              "slug": "kartopliani-chypsy-5021",
              "children": [],
              "total": 44
            },
            {
              "slug": "zlakovi-chypsy-5022",
              "children": [],
              "total": 25
            }
          ],
          "total": 111
        },
        {
          "slug": "grinky-sukharyky-khlibtsi-5023",
          "children": [
            {
              "slug": "sukharyky-i-grinky-5024",
              "children": [],
              "total": 3
            },
            {
              "slug": "khlibtsi-5025",
              "children": [],
              "total": 29
            }
          ],
          "total": 32
        },
        {
          "slug": "solomka-i-krekery-5026",
          "children": [
            {
              "slug": "solomka-solona-5027",
              "children": [],
              "total": 5
            },
            {
              "slug": "krekery-ta-solone-pechyvo-5028",
              "children": [],
              "total": 11
            }
          ],
          "total": 16
        },
        {
          "slug": "rybni-sneky-5029",
          "children": [],
          "total": 16
        },
        {
          "slug": "m-iasni-chypsy-i-sneky-5030",
          "children": [],
          "total": 9
        },
        {
          "slug": "syrni-sneky-5031",
          "children": [],
          "total": 5
        },
        {
          "slug": "soloni-gorishky-5032",
          "children": [],
          "total": 24
        },
        {
          "slug": "nasinnia-smazhene-5033",
          "children": [
            {
              "slug": "soniashnykove-nasinnia-5034",
              "children": [],
              "total": 4
            },
            {
              "slug": "garbuzove-nasinnia-5035",
              "children": [],
              "total": 1
            }
          ],
          "total": 5
        },
        {
          "slug": "kukurudziani-palychky-i-popkorn-5036",
          "children": [
            {
              "slug": "kukurudziani-palychky-5037",
              "children": [],
              "total": 8
            },
            {
              "slug": "popkorn-5038",
              "children": [],
              "total": 11
            },
            {
              "slug": "smazhena-kukurudza-5039",
              "children": [],
              "total": 1
            }
          ],
          "total": 20
        },
        {
          "slug": "batonchyky-5040",
          "children": [],
          "total": 46
        },
        {
          "slug": "sneky-z-gorikhiv-i-sukhofruktiv-5041",
          "children": []
        },
        {
          "slug": "korysni-perekusy-5042",
          "children": []
        }
      ],
      "total": 284
    },
    {
      "slug": "kava-chai-359",
      "children": [
        {
          "slug": "kava-5110",
          "children": [
            {
              "slug": "kava-v-zernakh-5111",
              "children": [],
              "total": 69
            },
            {
              "slug": "kava-v-kapsulakh-5112",
              "children": [],
              "total": 30
            },
            {
              "slug": "kava-vlasnogo-obsmazhennia-5113",
              "children": [],
              "total": 44
            },
            {
              "slug": "kava-melena-5114",
              "children": [],
              "total": 47
            },
            {
              "slug": "kava-rozchynna-5115",
              "children": [],
              "total": 10
            },
            {
              "slug": "kava-u-stikakh-5116",
              "children": []
            },
            {
              "slug": "drip-kava-5117",
              "children": [],
              "total": 24
            },
            {
              "slug": "bezkofeinova-kava-5118",
              "children": [],
              "total": 14
            },
            {
              "slug": "syropy-i-dobavky-do-kavy-5119",
              "children": [],
              "total": 2
            },
            {
              "slug": "vse-dlia-prygotuvannia-kavy-5120",
              "children": []
            }
          ],
          "total": 189
        },
        {
          "slug": "chai-5126",
          "children": [
            {
              "slug": "zelenyi-chai-5127",
              "children": [],
              "total": 46
            },
            {
              "slug": "chornyi-chai-5128",
              "children": [],
              "total": 62
            },
            {
              "slug": "trav-iani-fruktovi-plodovi-chai-5129",
              "children": [],
              "total": 82
            },
            {
              "slug": "osoblyvi-chai-5130",
              "children": [],
              "total": 25
            },
            {
              "slug": "chai-rozchynnyi-5131",
              "children": [],
              "total": 1
            },
            {
              "slug": "chai-vagovyi-5132",
              "children": [],
              "total": 47
            },
            {
              "slug": "chaini-nabory-ta-asorti-5133",
              "children": [],
              "total": 2
            },
            {
              "slug": "sumishi-chaiv-5134",
              "children": [],
              "total": 3
            },
            {
              "slug": "vse-dlia-prygotuvannia-chaiu-5135",
              "children": [],
              "total": 2
            }
          ],
          "total": 244
        },
        {
          "slug": "kakao-gariachyi-shokolad-360",
          "children": [],
          "total": 3
        },
        {
          "slug": "tsykorii-369",
          "children": [],
          "total": 4
        }
      ],
      "total": 440
    },
    {
      "slug": "napoi-52",
      "children": [
        {
          "slug": "voda-5087",
          "children": [
            {
              "slug": "negazovana-voda-5088",
              "children": [],
              "total": 39
            },
            {
              "slug": "slabogazovana-voda-5089",
              "children": [],
              "total": 9
            },
            {
              "slug": "sylnogazovana-voda-5090",
              "children": [],
              "total": 45
            },
            {
              "slug": "mineralna-voda-5091",
              "children": [],
              "total": 27
            },
            {
              "slug": "smakova-voda-5092",
              "children": [],
              "total": 15
            },
            {
              "slug": "voda-dytiacha-5093",
              "children": [],
              "total": 6
            },
            {
              "slug": "voda-butylovana-5094",
              "children": [],
              "total": 3
            }
          ],
          "total": 114
        },
        {
          "slug": "solodka-voda-56",
          "children": [
            {
              "slug": "solodka-voda-gazovana-5095",
              "children": [],
              "total": 157
            },
            {
              "slug": "smak-kola-5096",
              "children": [],
              "total": 20
            },
            {
              "slug": "lymonady-5097",
              "children": [],
              "total": 36
            },
            {
              "slug": "toniky-sodova-5098",
              "children": [],
              "total": 27
            },
            {
              "slug": "solodka-voda-negazovana-5099",
              "children": [],
              "total": 32
            },
            {
              "slug": "dytiache-shampanske-5100",
              "children": [],
              "total": 1
            }
          ],
          "total": 191
        },
        {
          "slug": "soky-i-nektary-5101",
          "children": [
            {
              "slug": "soky-5102",
              "children": [],
              "total": 139
            },
            {
              "slug": "nektary-5104",
              "children": [],
              "total": 43
            },
            {
              "slug": "smuzi-i-svizhovychavleni-soky-5105",
              "children": [],
              "total": 15
            },
            {
              "slug": "sokovmisni-napoi-5106",
              "children": [],
              "total": 22
            },
            {
              "slug": "morsy-5107",
              "children": [],
              "total": 4
            },
            {
              "slug": "kompoty-5108",
              "children": []
            }
          ],
          "total": 216
        },
        {
          "slug": "kvas-57",
          "children": [],
          "total": 6
        },
        {
          "slug": "kombucha-i-fermentovani-napoi-5109",
          "children": [],
          "total": 53
        },
        {
          "slug": "energetychni-napoi-59",
          "children": [],
          "total": 30
        },
        {
          "slug": "kholodni-chai-ta-kava-58",
          "children": [],
          "total": 9
        },
        {
          "slug": "syropy-dlia-kokteiliv-55",
          "children": []
        }
      ],
      "total": 616
    },
    {
      "slug": "zamorozhena-produktsiia-264",
      "children": [
        {
          "slug": "napivfabrykaty-i-stravy-zamorozheni-5168",
          "children": [
            {
              "slug": "pelmeni-5170",
              "children": [],
              "total": 13
            },
            {
              "slug": "khinkali-i-ravioli-5192",
              "children": [],
              "total": 18
            },
            {
              "slug": "varenyky-5171",
              "children": [],
              "total": 14
            },
            {
              "slug": "syrnyky-zamorozheni-5174",
              "children": [],
              "total": 16
            },
            {
              "slug": "mlyntsi-zamorozheni-5173",
              "children": [],
              "total": 4
            },
            {
              "slug": "gotovi-stravy-zamorozheni-5175",
              "children": [],
              "total": 18
            },
            {
              "slug": "m-iasni-ta-ovochevi-napivfabrykaty-5169",
              "children": [],
              "total": 24
            },
            {
              "slug": "sneky-zamorozheni-5182",
              "children": [],
              "total": 2
            },
            {
              "slug": "vypichka-zamorozhena-5172",
              "children": [],
              "total": 12
            }
          ],
          "total": 121
        },
        {
          "slug": "morozyvo-i-deserty-5176",
          "children": [
            {
              "slug": "morozyvo-5177",
              "children": [],
              "total": 64
            },
            {
              "slug": "deserty-i-torty-zamorozheni-5178",
              "children": [],
              "total": 40
            },
            {
              "slug": "morozyvo-vlasnogo-vyrobnytstva-5187",
              "children": [],
              "total": 16
            }
          ],
          "total": 104
        },
        {
          "slug": "ovochi-i-frukty-zamorozheni-5183",
          "children": [
            {
              "slug": "ovochi-zamorozheni-5184",
              "children": [],
              "total": 15
            },
            {
              "slug": "frukty-zamorozheni-5185",
              "children": []
            },
            {
              "slug": "yagody-zamorozheni-5186",
              "children": [],
              "total": 1
            },
            {
              "slug": "fruktovo-iagidni-sumishi-zamorozheni-5190",
              "children": []
            },
            {
              "slug": "gryby-zamorozheni-5191",
              "children": [],
              "total": 1
            }
          ],
          "total": 17
        },
        {
          "slug": "tisto-zamorozhene-274",
          "children": [],
          "total": 4
        },
        {
          "slug": "lid-267",
          "children": [],
          "total": 7
        },
        {
          "slug": "zamorozheni-chai-ta-napoi-5179",
          "children": []
        },
        {
          "slug": "zamorozhene-m-iaso-5180",
          "children": [],
          "total": 5
        },
        {
          "slug": "zamorozheni-moreprodukty-i-ryba-5181",
          "children": [],
          "total": 38
        }
      ],
      "total": 296
    },
    {
      "slug": "alkogol-22",
      "children": [
        {
          "slug": "mitsnyi-alkogol-4458",
          "children": [
            {
              "slug": "viski-4466",
              "children": [],
              "total": 535
            },
            {
              "slug": "koniak-brendi-4467",
              "children": [],
              "total": 151
            },
            {
              "slug": "rom-4468",
              "children": [],
              "total": 183
            },
            {
              "slug": "dzhyn-4469",
              "children": [],
              "total": 73
            },
            {
              "slug": "tekila-agavovi-dystyliaty-4470",
              "children": [],
              "total": 75
            },
            {
              "slug": "aziiskyi-alkogol-4471",
              "children": [],
              "total": 4
            },
            {
              "slug": "gorilka-4472",
              "children": [],
              "total": 148
            },
            {
              "slug": "nastoianky-nalyvky-4473",
              "children": [],
              "total": 21
            },
            {
              "slug": "likery-balzamy-bittery-4474",
              "children": [],
              "total": 95
            },
            {
              "slug": "drinksetter-4508",
              "children": [],
              "total": 154
            }
          ],
          "total": 1285
        },
        {
          "slug": "tykhi-vyna-4459",
          "children": [
            {
              "slug": "chervoni-vyna-4475",
              "children": [],
              "total": 653
            },
            {
              "slug": "bili-vyna-4476",
              "children": [],
              "total": 429
            },
            {
              "slug": "rozhevi-vyna-4502",
              "children": [],
              "total": 63
            },
            {
              "slug": "pomaranchevi-vyna-4477",
              "children": [],
              "total": 14
            },
            {
              "slug": "kripleni-vyna-kheres-kagor-ta-in-4501",
              "children": [],
              "total": 87
            },
            {
              "slug": "sangriia-ta-glintvein-4478",
              "children": [],
              "total": 1
            },
            {
              "slug": "plodovo-iagidni-vyna-4479",
              "children": [],
              "total": 2
            }
          ],
          "total": 1249
        },
        {
          "slug": "igrysti-vyna-ta-shampanske-4460",
          "children": [
            {
              "slug": "igrysti-vyna-4509",
              "children": [],
              "total": 68
            },
            {
              "slug": "shampanske-champagne-4510",
              "children": [],
              "total": 64
            },
            {
              "slug": "klasychnyi-metod-kreman-franchakorta-inshi-4511",
              "children": [],
              "total": 23
            },
            {
              "slug": "kava-cava-4512",
              "children": [],
              "total": 16
            },
            {
              "slug": "proseko-prosecco-4513",
              "children": [],
              "total": 40
            },
            {
              "slug": "asti-asti-4514",
              "children": [],
              "total": 7
            },
            {
              "slug": "lambrusko-lambrusco-4515",
              "children": [],
              "total": 1
            },
            {
              "slug": "fragolino-fragolino-4516",
              "children": [],
              "total": 2
            },
            {
              "slug": "pet-nat-pet-nat-4518",
              "children": [],
              "total": 5
            },
            {
              "slug": "igrysti-kokteili-4517",
              "children": [],
              "total": 6
            }
          ],
          "total": 369
        },
        {
          "slug": "vermuty-4461",
          "children": [],
          "total": 41
        },
        {
          "slug": "pyvo-4503",
          "children": [
            {
              "slug": "ukrainske-pyvo-4504",
              "children": [],
              "total": 16
            },
            {
              "slug": "importne-pyvo-4505",
              "children": [],
              "total": 338
            },
            {
              "slug": "kraftove-pyvo-4506",
              "children": [],
              "total": 61
            },
            {
              "slug": "vlasna-brovarnia-beermaster-brewery-4507",
              "children": [],
              "total": 7
            }
          ],
          "total": 422
        },
        {
          "slug": "slaboalkogolni-napoi-sydr-4463",
          "children": [
            {
              "slug": "sydr-ta-zbyten-4480",
              "children": [],
              "total": 59
            },
            {
              "slug": "alkoenergetyky-4481",
              "children": []
            },
            {
              "slug": "slaboalkogolni-kokteili-4482",
              "children": [],
              "total": 33
            }
          ],
          "total": 92
        },
        {
          "slug": "bezalkogolnyi-alkogol-4464",
          "children": [
            {
              "slug": "bezalkogolne-vyno-4483",
              "children": [],
              "total": 38
            },
            {
              "slug": "bezalkogolne-pyvo-4484",
              "children": [],
              "total": 21
            },
            {
              "slug": "bezalkogolni-mitsni-napoi-4485",
              "children": [],
              "total": 8
            },
            {
              "slug": "bezalkogolni-kokteili-4486",
              "children": [],
              "total": 5
            }
          ],
          "total": 72
        }
      ],
      "total": 3518
    },
    {
      "slug": "sygarety-stiky-zhuiky-4384",
      "children": [],
      "total": 335
    },
    {
      "slug": "kvity-tovary-dlia-sadu-ta-gorodu-476",
      "children": [
        {
          "slug": "grunty-dobryva-480",
          "children": []
        },
        {
          "slug": "kvity-3272",
          "children": [],
          "total": 6
        },
        {
          "slug": "tovary-dlia-sadu-ta-gorodu-478",
          "children": []
        },
        {
          "slug": "kimnatni-roslyny-4499",
          "children": [],
          "total": 2
        },
        {
          "slug": "gorshchyky-dlia-kvitiv-i-aksesuary-4500",
          "children": []
        },
        {
          "slug": "dekor-dlia-kvitiv-i-buketiv-5201",
          "children": [],
          "total": 10
        },
        {
          "slug": "sadzhantsi-nasinnia-482",
          "children": []
        }
      ],
      "total": 18
    },
    {
      "slug": "dlia-domu-567",
      "children": [
        {
          "slug": "pobutova-khimiia-4588",
          "children": [
            {
              "slug": "pralni-poroshky-geli-kapsuly-4589",
              "children": [],
              "total": 34
            },
            {
              "slug": "opoliskuvachi-dlia-bilyzny-4590",
              "children": [],
              "total": 26
            },
            {
              "slug": "pliamovyvidnyky-vidbiliuvachi-4591",
              "children": [],
              "total": 22
            },
            {
              "slug": "dlia-myttia-posudu-4592",
              "children": [],
              "total": 33
            },
            {
              "slug": "dlia-prybyrannia-4593",
              "children": [],
              "total": 52
            },
            {
              "slug": "osvizhuvachi-povitria-4594",
              "children": [],
              "total": 14
            },
            {
              "slug": "aromadyfuzory-4595",
              "children": [],
              "total": 54
            },
            {
              "slug": "insektytsydy-4596",
              "children": [],
              "total": 6
            },
            {
              "slug": "dogliad-za-vzuttiam-4597",
              "children": [],
              "total": 3
            }
          ],
          "total": 244
        },
        {
          "slug": "gospodarchi-tovary-4598",
          "children": [
            {
              "slug": "aksesuary-dlia-vanny-i-tualetu-4599",
              "children": []
            },
            {
              "slug": "pakety-dlia-smittia-4600",
              "children": [],
              "total": 18
            },
            {
              "slug": "gospodarchi-dribnytsi-4601",
              "children": [],
              "total": 15
            },
            {
              "slug": "gubky-skrebky-rukavychky-ganchirky-4602",
              "children": [],
              "total": 27
            },
            {
              "slug": "inventar-dlia-prybyrannia-4603",
              "children": [],
              "total": 4
            },
            {
              "slug": "folga-pergament-kharchova-plivka-4604",
              "children": [],
              "total": 13
            },
            {
              "slug": "batareiky-lampochky-likhtaryky-4605",
              "children": [],
              "total": 3
            },
            {
              "slug": "zapalnychky-sirnyky-4606",
              "children": [],
              "total": 6
            },
            {
              "slug": "dogliad-za-odiagom-i-vzuttiam-4607",
              "children": [],
              "total": 3
            },
            {
              "slug": "filtry-i-kartrydzhi-dlia-vody-4608",
              "children": []
            },
            {
              "slug": "pakety-sumky-ekotorbynky-4609",
              "children": [],
              "total": 40
            },
            {
              "slug": "dlia-avtomobiliv-4610",
              "children": [],
              "total": 14
            }
          ],
          "total": 143
        },
        {
          "slug": "paperovi-vyroby-4611",
          "children": [
            {
              "slug": "tualetnyi-papir-4612",
              "children": [],
              "total": 14
            },
            {
              "slug": "servetky-stolovi-4613",
              "children": [],
              "total": 8
            },
            {
              "slug": "paperovi-rushnyky-4614",
              "children": [],
              "total": 9
            },
            {
              "slug": "nosovi-servetky-4615",
              "children": [],
              "total": 4
            },
            {
              "slug": "servetky-v-korobtsi-4616",
              "children": [],
              "total": 5
            },
            {
              "slug": "vologi-servetky-4617",
              "children": [],
              "total": 7
            }
          ],
          "total": 47
        },
        {
          "slug": "odnorazovyi-posud-4618",
          "children": [
            {
              "slug": "sklianky-4619",
              "children": [],
              "total": 15
            },
            {
              "slug": "lozhky-vydelky-mishalky-nozhi-4620",
              "children": [],
              "total": 6
            },
            {
              "slug": "tarilky-4621",
              "children": [],
              "total": 16
            },
            {
              "slug": "nabory-posudu-4622",
              "children": [],
              "total": 1
            }
          ],
          "total": 38
        },
        {
          "slug": "posud-4633",
          "children": [
            {
              "slug": "tarilky-mysky-i-salatnyky-4634",
              "children": [],
              "total": 57
            },
            {
              "slug": "dlia-prygotuvannia-chaiu-kavy-4635",
              "children": [],
              "total": 12
            },
            {
              "slug": "stolovi-prybory-4636",
              "children": [],
              "total": 2
            },
            {
              "slug": "chashky-kelykhy-sklianky-4637",
              "children": [],
              "total": 51
            },
            {
              "slug": "formy-dlia-vypikannia-4638",
              "children": [],
              "total": 6
            },
            {
              "slug": "skovoridky-kastruli-4639",
              "children": [],
              "total": 8
            },
            {
              "slug": "kukhonni-nozhi-4640",
              "children": [],
              "total": 23
            },
            {
              "slug": "kukhonne-nachynnia-4641",
              "children": [],
              "total": 65
            },
            {
              "slug": "barni-aksesuary-4642",
              "children": [],
              "total": 55
            },
            {
              "slug": "dlia-zberigannia-produktiv-4643",
              "children": [],
              "total": 21
            }
          ],
          "total": 300
        },
        {
          "slug": "domashnii-tekstyl-4644",
          "children": [],
          "total": 8
        },
        {
          "slug": "tovary-dlia-sviat-4623",
          "children": [
            {
              "slug": "dlia-dniv-narodzhen-i-vechirok-4624",
              "children": [],
              "total": 35
            },
            {
              "slug": "podarunkova-upakovka-lystivky-4625",
              "children": [],
              "total": 67
            },
            {
              "slug": "tematychni-sviata-4626",
              "children": [],
              "total": 79
            },
            {
              "slug": "solomynky-i-shpazhky-4627",
              "children": [],
              "total": 3
            },
            {
              "slug": "sviatkovyi-posud-i-aksesuary-4628",
              "children": []
            }
          ],
          "total": 184
        },
        {
          "slug": "inter-ier-4629",
          "children": [
            {
              "slug": "svichky-i-pidsvichnyky-4630",
              "children": [],
              "total": 100
            },
            {
              "slug": "dekoratyvni-podushky-4632",
              "children": []
            },
            {
              "slug": "aromaty-dlia-domu-4667",
              "children": []
            },
            {
              "slug": "vazy-kartyny-i-dekor-4631",
              "children": [],
              "total": 26
            }
          ],
          "total": 126
        },
        {
          "slug": "odiag-i-aksesuary-4645",
          "children": [
            {
              "slug": "kolgotky-4646",
              "children": [],
              "total": 83
            },
            {
              "slug": "shkarpetky-4647",
              "children": [],
              "total": 24
            },
            {
              "slug": "vzuttia-i-domashni-kaptsi-4648",
              "children": []
            },
            {
              "slug": "valizy-i-sumky-4649",
              "children": []
            },
            {
              "slug": "golovni-ubory-i-aksesuary-4650",
              "children": []
            },
            {
              "slug": "bilyzna-4651",
              "children": []
            }
          ],
          "total": 107
        },
        {
          "slug": "pobutova-tekhnika-i-elektronika-4652",
          "children": [],
          "total": 11
        },
        {
          "slug": "kantseliariia-knygy-zhurnaly-4653",
          "children": [
            {
              "slug": "ruchky-olivtsi-markery-4654",
              "children": []
            },
            {
              "slug": "kantseliarski-aksesuary-4655",
              "children": []
            },
            {
              "slug": "papir-4656",
              "children": []
            },
            {
              "slug": "zoshyty-notatnyky-albomy-4657",
              "children": [],
              "total": 86
            },
            {
              "slug": "rozmalovky-5440",
              "children": [],
              "total": 1
            },
            {
              "slug": "penaly-portfeli-rantsi-vizytnytsi-4658",
              "children": []
            },
            {
              "slug": "dytiachi-kantstovary-4659",
              "children": [],
              "total": 12
            },
            {
              "slug": "zhurnaly-i-gazety-4660",
              "children": [],
              "total": 3
            },
            {
              "slug": "knygy-4661",
              "children": [],
              "total": 111
            },
            {
              "slug": "startovi-pakety-kartky-4662",
              "children": [],
              "total": 5
            }
          ],
          "total": 218
        },
        {
          "slug": "piknik-i-vidpochynok-4663",
          "children": [
            {
              "slug": "mangaly-i-reshitky-dlia-gryliu-4664",
              "children": [],
              "total": 33
            },
            {
              "slug": "vugillia-drova-rozpaliuvachi-4665",
              "children": [],
              "total": 36
            },
            {
              "slug": "dlia-turyzmu-i-sportu-4666",
              "children": [],
              "total": 34
            }
          ],
          "total": 103
        }
      ],
      "total": 1529
    },
    {
      "slug": "gigiiena-ta-krasa-4519",
      "children": [
        {
          "slug": "osobysta-gigiiena-ta-zdorov-ia-4527",
          "children": [
            {
              "slug": "zubna-pasta-ta-opoliskuvachi-4566",
              "children": [],
              "total": 49
            },
            {
              "slug": "zubni-shchitky-ta-nytka-4567",
              "children": [],
              "total": 41
            },
            {
              "slug": "elektrychni-zubni-shchitky-4568",
              "children": [],
              "total": 4
            },
            {
              "slug": "prokladky-tampony-dlia-intymnoi-gigiieny-4569",
              "children": [],
              "total": 48
            },
            {
              "slug": "vatni-dysky-ta-palychky-4571",
              "children": [],
              "total": 6
            },
            {
              "slug": "dlia-intymnogo-zhyttia-4572",
              "children": [],
              "total": 3
            },
            {
              "slug": "vologi-servetky-4574",
              "children": [],
              "total": 7
            },
            {
              "slug": "nosovi-servetky-4575",
              "children": [],
              "total": 4
            },
            {
              "slug": "servetky-v-korobtsi-4576",
              "children": [],
              "total": 8
            },
            {
              "slug": "pidguzky-dlia-doroslykh-4570",
              "children": []
            },
            {
              "slug": "antyseptyky-masky-plastyri-inshe-4573",
              "children": [],
              "total": 4
            }
          ],
          "total": 174
        },
        {
          "slug": "dogliad-za-tilom-4522",
          "children": [
            {
              "slug": "geli-dlia-dushu-4536",
              "children": [],
              "total": 76
            },
            {
              "slug": "krem-dlia-tila-4537",
              "children": [],
              "total": 74
            },
            {
              "slug": "dezodoranty-4542",
              "children": [],
              "total": 48
            },
            {
              "slug": "mylo-4538",
              "children": [],
              "total": 37
            },
            {
              "slug": "pina-sil-bombochky-dlia-vanny-4540",
              "children": [],
              "total": 5
            },
            {
              "slug": "skrab-dlia-tila-4541",
              "children": [],
              "total": 28
            },
            {
              "slug": "mochalky-dlia-dushu-4539",
              "children": [],
              "total": 4
            },
            {
              "slug": "kosmetychni-masky-4587",
              "children": [],
              "total": 23
            }
          ],
          "total": 295
        },
        {
          "slug": "dogliad-za-oblychchiam-4523",
          "children": [
            {
              "slug": "krem-i-syrovatka-dlia-oblychchia-4545",
              "children": [],
              "total": 58
            },
            {
              "slug": "dlia-vmyvannia-i-demakiiazhu-4546",
              "children": [],
              "total": 27
            },
            {
              "slug": "masky-dlia-oblychchia-patchi-4543",
              "children": [],
              "total": 1
            },
            {
              "slug": "skraby-dlia-oblychchia-4547",
              "children": []
            },
            {
              "slug": "dogliad-za-gubamy-4544",
              "children": [],
              "total": 12
            }
          ],
          "total": 98
        },
        {
          "slug": "dogliad-za-volossiam-4524",
          "children": [
            {
              "slug": "shampuni-4548",
              "children": [],
              "total": 60
            },
            {
              "slug": "kondytsionery-dlia-volossia-4549",
              "children": [],
              "total": 31
            },
            {
              "slug": "masky-dlia-volossia-4550",
              "children": [],
              "total": 13
            },
            {
              "slug": "zasoby-dlia-ukladky-4551",
              "children": [],
              "total": 3
            },
            {
              "slug": "spetsialnyi-dogliad-4553",
              "children": [],
              "total": 20
            },
            {
              "slug": "aksesuary-dlia-volossia-4554",
              "children": [],
              "total": 7
            },
            {
              "slug": "farba-dlia-volossia-4555",
              "children": []
            }
          ],
          "total": 134
        },
        {
          "slug": "dlia-golinnia-i-depiliatsii-4526",
          "children": [
            {
              "slug": "brytvy-i-leza-4561",
              "children": [],
              "total": 8
            },
            {
              "slug": "zasoby-dlia-golinnia-4562",
              "children": [],
              "total": 19
            },
            {
              "slug": "zasoby-pislia-golinnia-4563",
              "children": [],
              "total": 12
            },
            {
              "slug": "dlia-depiliatsii-4564",
              "children": [],
              "total": 1
            },
            {
              "slug": "dogliad-za-borodoiu-i-vusamy-4565",
              "children": [],
              "total": 7
            }
          ],
          "total": 47
        },
        {
          "slug": "dogliad-za-rukamy-i-nogamy-4525",
          "children": [
            {
              "slug": "krem-dlia-ruk-i-nig-4556",
              "children": [],
              "total": 50
            },
            {
              "slug": "masky-dlia-ruk-i-nig-4557",
              "children": []
            },
            {
              "slug": "dogliad-za-nigtiamy-ta-kutykuloiu-4558",
              "children": []
            },
            {
              "slug": "manikiur-pedykiur-4559",
              "children": []
            },
            {
              "slug": "dezodoranty-dlia-nig-4560",
              "children": []
            }
          ],
          "total": 50
        },
        {
          "slug": "dlia-cholovikiv-4520",
          "children": [
            {
              "slug": "dezodoranty-dlia-cholovikiv-4530",
              "children": [],
              "total": 16
            },
            {
              "slug": "dlia-vanny-i-dushu-4531",
              "children": [],
              "total": 4
            },
            {
              "slug": "dlia-volossia-ta-borody-4532",
              "children": [],
              "total": 1
            },
            {
              "slug": "dogliadova-kosmetyka-4533",
              "children": [],
              "total": 1
            },
            {
              "slug": "golinnia-4534",
              "children": [],
              "total": 18
            },
            {
              "slug": "prezervatyvy-ta-lubrykanty-4535",
              "children": [],
              "total": 3
            }
          ],
          "total": 43
        },
        {
          "slug": "podarunkovi-nabory-4529",
          "children": [],
          "total": 25
        },
        {
          "slug": "dekoratyvna-kosmetyka-4528",
          "children": [
            {
              "slug": "zasoby-dlia-zniattia-makiiazhu-4577",
              "children": []
            },
            {
              "slug": "kosmetyka-4578",
              "children": []
            },
            {
              "slug": "aksesuary-dlia-makiiazhu-4579",
              "children": []
            }
          ]
        },
        {
          "slug": "sontsezakhysni-zasoby-4521",
          "children": [],
          "total": 9
        }
      ],
      "total": 831
    },
    {
      "slug": "dytiachi-tovary-449",
      "children": [
        {
          "slug": "dytiache-kharchuvannia-4676",
          "children": [
            {
              "slug": "piure-dytiachi-4677",
              "children": [],
              "total": 94
            },
            {
              "slug": "sumishi-dytiachi-4678",
              "children": [],
              "total": 28
            },
            {
              "slug": "kashi-dytiachi-4679",
              "children": [],
              "total": 29
            },
            {
              "slug": "supchyky-dytiachi-4680",
              "children": [],
              "total": 3
            },
            {
              "slug": "soky-i-napoi-dytiachi-4681",
              "children": [],
              "total": 27
            },
            {
              "slug": "pechyvo-i-sneky-dytiachi-4682",
              "children": [],
              "total": 22
            },
            {
              "slug": "dytiachi-iogurty-i-kefir-4683",
              "children": [],
              "total": 20
            },
            {
              "slug": "makarony-dytiachi-4684",
              "children": []
            }
          ],
          "total": 223
        },
        {
          "slug": "tovary-dlia-goduvannia-4668",
          "children": [
            {
              "slug": "dytiachi-pliashechky-i-poilnyky-4709",
              "children": []
            },
            {
              "slug": "dytiachi-sosky-i-pustushky-4708",
              "children": []
            },
            {
              "slug": "dytiachyi-posud-4707",
              "children": []
            },
            {
              "slug": "aksesuary-dlia-goduvannia-4706",
              "children": []
            }
          ]
        },
        {
          "slug": "pidguzky-i-peliushky-4669",
          "children": [
            {
              "slug": "pidguzky-trusyky-4705",
              "children": [],
              "total": 8
            },
            {
              "slug": "pidguzky-4704",
              "children": []
            },
            {
              "slug": "peliushky-4703",
              "children": [],
              "total": 1
            }
          ],
          "total": 9
        },
        {
          "slug": "dytiachi-vologi-servertky-4671",
          "children": [],
          "total": 7
        },
        {
          "slug": "dytiacha-kosmetyka-i-dogliad-4670",
          "children": [
            {
              "slug": "dogliad-za-zubkamy-4702",
              "children": [],
              "total": 16
            },
            {
              "slug": "dytiache-kupannia-4701",
              "children": [],
              "total": 8
            },
            {
              "slug": "kremy-oliiky-prysypky-4700",
              "children": [],
              "total": 1
            },
            {
              "slug": "sezonna-dytiacha-kosmetyka-4699",
              "children": []
            },
            {
              "slug": "asksesuary-dlia-dogliadu-4698",
              "children": []
            }
          ],
          "total": 25
        },
        {
          "slug": "dytiacha-pobutova-khimiia-4672",
          "children": []
        },
        {
          "slug": "igrashky-ta-knygy-4673",
          "children": [
            {
              "slug": "igrashky-4697",
              "children": [],
              "total": 3
            },
            {
              "slug": "m-iaki-igrashky-4696",
              "children": []
            },
            {
              "slug": "konstruktory-4695",
              "children": [],
              "total": 10
            },
            {
              "slug": "dytiacha-tvorchist-ta-igry-4694",
              "children": []
            },
            {
              "slug": "igrashky-dlia-naimenshykh-4693",
              "children": []
            },
            {
              "slug": "kolektsiini-igrashky-silpo-4692",
              "children": [],
              "total": 1
            },
            {
              "slug": "dytiachi-knygy-4691",
              "children": [],
              "total": 24
            },
            {
              "slug": "rozmalovky-dlia-ditei-5441",
              "children": [],
              "total": 1
            },
            {
              "slug": "shkilne-pryladdia-ta-kantseliariia-4690",
              "children": []
            },
            {
              "slug": "rozvagy-na-svizhomu-povitri-4689",
              "children": []
            }
          ],
          "total": 37
        },
        {
          "slug": "dytiachyi-odiag-vzuttia-tekstyl-4674",
          "children": [
            {
              "slug": "dytiachi-shkarpetky-4688",
              "children": [],
              "total": 1
            },
            {
              "slug": "dytiachi-kolgotky-4687",
              "children": []
            },
            {
              "slug": "dytiachi-golovni-ubory-i-aksesuary-4686",
              "children": []
            },
            {
              "slug": "dytiache-vzuttia-4685",
              "children": []
            }
          ],
          "total": 1
        },
        {
          "slug": "tovary-dlia-mam-4675",
          "children": [],
          "total": 2
        }
      ],
      "total": 303
    },
    {
      "slug": "dlia-tvaryn-653",
      "children": [
        {
          "slug": "dlia-kotiv-4710",
          "children": [
            {
              "slug": "korm-dlia-kotiv-4711",
              "children": [],
              "total": 57
            },
            {
              "slug": "napovniuvachi-i-kotiachi-tualety-4712",
              "children": [],
              "total": 12
            },
            {
              "slug": "aksesuary-ta-igrashky-dlia-kotiv-4713",
              "children": []
            }
          ],
          "total": 69
        },
        {
          "slug": "dlia-sobak-4714",
          "children": [
            {
              "slug": "korm-dlia-sobak-4715",
              "children": [],
              "total": 26
            },
            {
              "slug": "aksesuary-ta-igrashky-dlia-sobak-4716",
              "children": [],
              "total": 1
            },
            {
              "slug": "peliushky-i-tualety-dlia-sobak-4717",
              "children": []
            },
            {
              "slug": "farsh-dlia-tvaryn-4729",
              "children": []
            }
          ],
          "total": 27
        },
        {
          "slug": "dlia-ryb-ta-reptylii-4718",
          "children": []
        },
        {
          "slug": "dlia-papug-ta-ptakhiv-4719",
          "children": [
            {
              "slug": "korm-dlia-papug-i-ptakhiv-4720",
              "children": []
            },
            {
              "slug": "aksesuary-ta-igrashky-dlia-ptakhiv-4721",
              "children": []
            },
            {
              "slug": "napovniuvachi-i-pidstylka-dlia-ptakhiv-4722",
              "children": []
            }
          ]
        },
        {
          "slug": "dlia-gryzuniv-4723",
          "children": [
            {
              "slug": "korm-dlia-gryzuniv-4724",
              "children": []
            },
            {
              "slug": "pidstylka-ta-pisok-dlia-gryzuniv-4725",
              "children": []
            },
            {
              "slug": "aksesuary-igrashky-ta-budynochky-4726",
              "children": []
            }
          ]
        },
        {
          "slug": "gruming-4727",
          "children": [],
          "total": 3
        }
      ],
      "total": 99
    }
  ]
}


#### product_sets

{
  "success": true,
  "summary": "Found 17 product sets",
  "sets": [
    {
      "slug": "klatsniznyzhky",
      "title": "Тільки онлайн",
      "description": null,
      "link": "https://silpo.ua/sets/klatsniznyzhky"
    },
    {
      "slug": "dlia-smachnoi-vecheri",
      "title": "До смачного перегляду",
      "description": null,
      "link": "https://silpo.ua/sets/dlia-smachnoi-vecheri"
    },
    {
      "slug": "smakuizmorshynska",
      "title": "Смакуй з Моршинська",
      "description": null,
      "link": "https://silpo.ua/sets/smakuizmorshynska"
    },
    {
      "slug": "pitsa-sushi-ta-burhery",
      "title": "Піца, суші та бургери",
      "description": null,
      "link": "https://silpo.ua/sets/pitsa-sushi-ta-burhery"
    },
    {
      "slug": "ferma",
      "title": "Знижки від ТМ Ферма",
      "description": null,
      "link": "https://silpo.ua/sets/ferma"
    },
    {
      "slug": "vyno-vivino",
      "title": "Вино з рейтингом Vivino",
      "description": null,
      "link": "https://silpo.ua/sets/vyno-vivino"
    },
    {
      "slug": "washandfree",
      "title": "Знижки на Wash&Free",
      "description": null,
      "link": "https://silpo.ua/sets/washandfree"
    },
    {
      "slug": "pepsi",
      "title": "Чемні чи бешкетні",
      "description": null,
      "link": "https://silpo.ua/sets/pepsi"
    },
    {
      "slug": "huggies-sales",
      "title": "Знижки від ТМ Huggies",
      "description": null,
      "link": "https://silpo.ua/sets/huggies-sales"
    },
    {
      "slug": "henkel-sale",
      "title": "Знижки до -64% на улюблені бренди Henkel",
      "description": null,
      "link": "https://silpo.ua/sets/henkel-sale"
    },
    {
      "slug": "zewa-sale",
      "title": "Zewa - відчуття турботи",
      "description": null,
      "link": "https://silpo.ua/sets/zewa-sale"
    },
    {
      "slug": "dlia-lehkykh-momentiv",
      "title": "Для легких моментів",
      "description": null,
      "link": "https://silpo.ua/sets/dlia-lehkykh-momentiv"
    },
    {
      "slug": "lvivske-310",
      "title": "Львівське 310",
      "description": null,
      "link": "https://silpo.ua/sets/lvivske-310"
    },
    {
      "slug": "super-znyzhky-na-pobutovu-khimiiu",
      "title": "Супер знижки на побутову хімію",
      "description": null,
      "link": "https://silpo.ua/sets/super-znyzhky-na-pobutovu-khimiiu"
    },
    {
      "slug": "promo-kosmetyka",
      "title": "Повернемо 50% балобонусами",
      "description": null,
      "link": "https://silpo.ua/sets/promo-kosmetyka"
    },
    {
      "slug": "ygotynske",
      "title": "Знижки від ТМ Яготинське",
      "description": null,
      "link": "https://silpo.ua/sets/ygotynske"
    },
    {
      "slug": "ekskliuzyvnoonlain",
      "title": "Ексклюзивні знижки онлайн",
      "description": null,
      "link": "https://silpo.ua/sets/ekskliuzyvnoonlain"
    }
  ]
}


#### promotions

{
  "success": true,
  "summary": "Found 5 active promotions",
  "promotions": [
    {
      "code": "only_online",
      "title": "Тільки Онлайн",
      "productCount": 1511,
      "url": "https://silpo.ua/offers/only_online"
    },
    {
      "code": "melkoopt",
      "title": "Гуртом дешевше",
      "productCount": 387,
      "url": "https://silpo.ua/offers/melkoopt"
    },
    {
      "code": "cinotyzhyky",
      "title": "Цінотижики",
      "productCount": 47,
      "url": "https://silpo.ua/offers/cinotyzhyky"
    },
    {
      "code": "monstr-rozihrash",
      "title": "Розіграш Монстр",
      "productCount": 7,
      "url": "https://silpo.ua/offers/monstr-rozihrash"
    },
    {
      "code": "kupuy_ta_zaoshadjuy",
      "title": "Купуй та заощаджуй",
      "productCount": 6,
      "url": "https://silpo.ua/offers/kupuy_ta_zaoshadjuy"
    }
  ]
}


#### products_mustHavePromotion

{
  "success": true,
  "summary": "Found 1957 products (showing 20)",
  "products": [
    {
      "id": "1ed075e6-dcfb-6928-829a-dd63763181f9",
      "name": "Тунець стейк свіжоморожений",
      "slug": "tunets-steik-svizhomorozhenyi-126071",
      "price": 399,
      "oldPrice": 539,
      "stock": 17,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/6af209c1-8b98-4728-8067-308bab9c8ed4.png",
      "weighted": true,
      "step": 0.5,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 126071
    },
    {
      "id": "1eeaf43a-c4bc-66f4-8330-79169448aff8",
      "name": "Томат Azura Чері сливка",
      "slug": "tomat-azura-cheri-slyvka-943334",
      "price": 89.1,
      "oldPrice": 99,
      "stock": 21,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/6bf41b31-4d05-4d0c-8ef3-f1131f99b334.png",
      "weighted": false,
      "step": 1,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 943334
    },
    {
      "id": "1ed075db-b311-6b04-a558-dd63763181f9",
      "name": "Перець жовтий",
      "slug": "perets-zhovtyi-32885",
      "price": 153.12,
      "oldPrice": 174,
      "stock": 2.75,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/2b106596-686b-46a1-b968-d8e30877bd19.png",
      "weighted": true,
      "step": 0.25,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 32885
    },
    {
      "id": "1ed07697-b48b-614e-925f-c1af87aa927f",
      "name": "Сік Feels good апельсиновий прямого віджиму",
      "slug": "sik-feels-good-apelsynovyi-priamogo-vidzhymu-863640",
      "price": 128.79,
      "oldPrice": 159,
      "stock": 5,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/88421264-8adf-4706-b6a8-59997d21bfab.png",
      "weighted": false,
      "step": 1,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 863640
    },
    {
      "id": "1ef4f8fb-1936-63fa-9cbb-b12fba711d88",
      "name": "Йогурт Bakoma MEN SKYR протеїновий зі смаком манго-маракуя 2%",
      "slug": "yogurt-bakoma-men-skyr-proteinovyi-zi-smakom-mango-marakuia-2-961301",
      "price": 62.9,
      "oldPrice": 89.99,
      "stock": 3,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/4530d205-c355-4bce-b627-aefa9a747c31.png",
      "weighted": false,
      "step": 1,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 961301
    },
    {
      "id": "1ed07695-3685-68a0-bf8f-c1af87aa927f",
      "name": "Сир Крафтяр Сулугуні палички копчені",
      "slug": "syr-kraftiar-suluguni-palychky-kopcheni-861134",
      "price": 399,
      "oldPrice": 699,
      "stock": 2.7,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/db2e11ae-9a5e-4599-9f65-7cadf6f13f8f.png",
      "weighted": true,
      "step": 0.3,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 861134
    },
    {
      "id": "1efeb38b-56a3-6982-b087-81142ab276ab",
      "name": "Серветки паперові Nua 3-шарові",
      "slug": "servetky-paperovi-nua-3-sharovi-979730",
      "price": 59.99,
      "oldPrice": 129,
      "stock": 19,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/86545849-326a-45d7-ab79-347b002e8412.png",
      "weighted": false,
      "step": 1,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 979730
    },
    {
      "id": "1ed0767c-bb7e-6b06-be60-eb0bb71c4ffc",
      "name": "Виноград Ред Глоб елітний рожевий",
      "slug": "vynograd-red-glob-elitnyi-rozhevyi-806770",
      "price": 279.46,
      "oldPrice": 314,
      "stock": 9,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/780a83ee-b687-49cf-925e-6b221a170923.png",
      "weighted": true,
      "step": 0.75,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 806770
    },
    {
      "id": "1ed075e8-1b2e-69f6-bbe6-dd63763181f9",
      "name": "Пиво Pilsner Urquell світле з/б",
      "slug": "pyvo-pilsner-urquell-svitle-z-b-137320",
      "price": 99,
      "oldPrice": 134,
      "stock": 26,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/95baab89-9ad1-4006-bb9f-3c3d1ddbc536.png",
      "weighted": false,
      "step": 1,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 137320
    },
    {
      "id": "1ed075ed-91e2-616a-9289-dd63763181f9",
      "name": "Шоколад молочний Toblerone з нугою, медом та мигдалем",
      "slug": "shokolad-molochnyi-toblerone-z-nugoiu-medom-ta-mygdalem-232729",
      "price": 84.99,
      "oldPrice": 144,
      "stock": 8,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/c3c50c68-1a44-4235-a220-0daf15d7181b.png",
      "weighted": false,
      "step": 1,
      "specialPrices": null,
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-


#### product_details

{
  "success": true,
  "product": {
    "id": "1ed075e6-dcfb-6928-829a-dd63763181f9",
    "name": "Тунець стейк свіжоморожений",
    "slug": "tunets-steik-svizhomorozhenyi-126071",
    "price": 399,
    "oldPrice": 539,
    "stock": 17,
    "available": true,
    "weighted": false,
    "step": 0.5,
    "ratio": "кг",
    "url": "https://silpo.ua/product/tunets-steik-svizhomorozhenyi-126071",
    "images": [
      "https://images.silpo.ua/v2/products/500x500/webp/6af209c1-8b98-4728-8067-308bab9c8ed4.png",
      "https://images.silpo.ua/v2/products/500x500/webp/d98a380f-d6dd-4c7b-a7b8-f035d285443e.png",
      "https://images.silpo.ua/v2/products/500x500/webp/73185c68-d9b3-477d-9b2c-ef28d22a8e5e.png"
    ],
    "attributes": {
      "Країна": "В'єтнам",
      "Торгова марка": "Без ТМ",
      "Продавець": "ТОВ «СІЛЬПО-ФУД»"
    },
    "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
    "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564"
  }
}


#### products_melkoopt

{
  "success": true,
  "summary": "Found 387 products (showing 15)",
  "products": [
    {
      "id": "1ed09877-b528-699c-b5de-c1af87aa927f",
      "name": "Снек Oreo молочний",
      "slug": "snek-oreo-molochnyi-868167",
      "price": 37.99,
      "oldPrice": null,
      "stock": 57,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/6baa7f25-0086-4941-b755-ce86f9969bcf.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 18.99,
          "count": 3,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 868167
    },
    {
      "id": "1ed076a1-41aa-6bac-a07e-e902eb641b79",
      "name": "Горіх волоський ядро екстра",
      "slug": "gorikh-voloskyi-iadro-ekstra-875393",
      "price": 169,
      "oldPrice": null,
      "stock": 22,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/810b71a8-8056-4c05-854e-4e1f1b43f43f.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 123.37,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 875393
    },
    {
      "id": "1ed075e9-911c-6112-849c-dd63763181f9",
      "name": "Шкребок стальний «Фрекен Бок»",
      "slug": "shkrebok-stalnyi-freken-bok-175280",
      "price": 29.99,
      "oldPrice": null,
      "stock": 15,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/bdb30b48-1eac-4211-be47-f1210cf70404.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 19,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 175280
    },
    {
      "id": "1ed07658-32b0-65fa-a754-c1af87aa927f",
      "name": "Зефір «Богуславна» з ароматом ванілі",
      "slug": "zefir-boguslavna-z-aromatom-vanili-702729",
      "price": 94.99,
      "oldPrice": null,
      "stock": 3,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/55ac0217-8128-4f3e-9379-fd08b0e36840.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 39.99,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 702729
    },
    {
      "id": "1ee59963-78cd-6e3c-96ae-17e94b97a0da",
      "name": "Йогурт Ростишка банан 2%, стакан",
      "slug": "yogurt-rostyshka-banan-2-stakan-937691",
      "price": 18.49,
      "oldPrice": null,
      "stock": 9,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/6a7b6cb2-6c77-487e-8d7b-9c4fbf436756.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 15.69,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 937691
    },
    {
      "id": "1ee59963-796b-6344-b4e9-711969710676",
      "name": "Йогурт Ростишка персик 2%, стакан",
      "slug": "yogurt-rostyshka-persyk-2-stakan-937690",
      "price": 18.49,
      "oldPrice": null,
      "stock": 11,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/0f08fc92-ef60-4165-b678-e91aac382dd6.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 15.69,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 937690
    },
    {
      "id": "1ee59963-68e5-6eca-abbd-dbee81ee8f8f",
      "name": "Йогурт Ростишка полуниця 2%, стакан",
      "slug": "yogurt-rostyshka-polunytsia-2-stakan-937687",
      "price": 18.49,
      "oldPrice": null,
      "stock": 22,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/9571b087-eedf-45db-9fe3-97a443031264.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 15.69,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 937687
    },
    {
      "id": "1ed07625-a3ec-6260-9439-dd63763181f9",
      "name": "Буряк «Грінвіль» по-корейськи",
      "slug": "buriak-grinvil-po-koreisky-555443",
      "price": 42.49,
      "oldPrice": null,
      "stock": 8,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/dd2d1f06-9d53-47de-9d15-248184ebae8f.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 28.89,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 555443
    },
    {
      "id": "1ef448ca-7fa7-645e-aecc-6f660dae0316",
      "name": "Мигдаль «Премія»® ядра горіхів сушені",
      "slug": "mygdal-premiia-iadra-gorikhiv-susheni-959560",
      "price": 84.99,
      "oldPrice": null,
      "stock": 30,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/2db70c96-5576-4aaf-96e9-b6a49a00f6c7.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 60.34,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 959560
    },
    {
      "id": "1edaed63-2e75-6d78-8f8e-c596f8a4e92f",
      "name": "Родзинки",
      "slug": "rodzynky-200688",
      "price": 82.49,
      "oldPrice": null,
      "stock": 24,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/72dd60da-9888-4d39-bcf9-5f75af79ce48.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 60.22,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 200688
    },
    {
      "id": "1ed076a3-2cee-690a-b3c5-c1af87aa927f",
      "name": "Манго «Премія»® сушене",
      "slug": "mango-premiia-sushene-881146",
      "price": 199,
      "oldPrice": null,
      "stock": 6,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/3e7c24fe-aa16-4502-8b82-3d5eb9adc788.png",
      "weighted": false,
      "step": 1,
      "specialPrices": [
        {
          "price": 99,
          "count": 2,
          "type": "from"
        }
      ],
      "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
      "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
      "externalProductId": 881146
    },
    {
      "id": "1ed0762c-2ed0-65e2-8fc2-dd63763181f9",
      "name": "Сир «Премія»® Маасдам 45%",
      "slug": "syr-premiia-maasdam-45-571255",
      "price": 689,
      "oldPrice": null,
      "stock": 24.25,
      "available": true,
      "image": "https://images.silpo.ua/v2/products/500x500/webp/0ff801a8-10d4-4ea2-af7d-b51015bb1641.png",
      "weighted": true,
      "step": 0.25,
      "specialPrices": [
        {
          "


#### melkoopt: total=15, with_specialPrices=15

```json
[
  {
    "id": "1ed09877-b528-699c-b5de-c1af87aa927f",
    "name": "Снек Oreo молочний",
    "slug": "snek-oreo-molochnyi-868167",
    "price": 37.99,
    "oldPrice": null,
    "stock": 57,
    "available": true,
    "image": "https://images.silpo.ua/v2/products/500x500/webp/6baa7f25-0086-4941-b755-ce86f9969bcf.png",
    "weighted": false,
    "step": 1,
    "specialPrices": [
      {
        "price": 18.99,
        "count": 3,
        "type": "from"
      }
    ],
    "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
    "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
    "externalProductId": 868167
  },
  {
    "id": "1ed076a1-41aa-6bac-a07e-e902eb641b79",
    "name": "Горіх волоський ядро екстра",
    "slug": "gorikh-voloskyi-iadro-ekstra-875393",
    "price": 169,
    "oldPrice": null,
    "stock": 22,
    "available": true,
    "image": "https://images.silpo.ua/v2/products/500x500/webp/810b71a8-8056-4c05-854e-4e1f1b43f43f.png",
    "weighted": false,
    "step": 1,
    "specialPrices": [
      {
        "price": 123.37,
        "count": 2,
        "type": "from"
      }
    ],
    "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
    "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
    "externalProductId": 875393
  },
  {
    "id": "1ed075e9-911c-6112-849c-dd63763181f9",
    "name": "Шкребок стальний «Фрекен Бок»",
    "slug": "shkrebok-stalnyi-freken-bok-175280",
    "price": 29.99,
    "oldPrice": null,
    "stock": 15,
    "available": true,
    "image": "https://images.silpo.ua/v2/products/500x500/webp/bdb30b48-1eac-4211-be47-f1210cf70404.png",
    "weighted": false,
    "step": 1,
    "specialPrices": [
      {
        "price": 19,
        "count": 2,
        "type": "from"
      }
    ],
    "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
    "branchId": "1edb6b38-214b-66d6-a8e0-7f2fdd178564",
    "externalProductId": 175280
  }
]
```
