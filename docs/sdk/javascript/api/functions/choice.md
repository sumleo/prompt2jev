# Function: choice()

```ts theme={null}
function choice<T>(instructions, criteria): ChoiceQuestion<T>;
```

Create a question that selects between named alternatives.

## Type Parameters

### T

`T` *extends* [`ChoiceCriteria`](../type-aliases/ChoiceCriteria.md)

## Parameters

### instructions

[`EntryType`](../type-aliases/EntryType.md)

The question as text, a JSON object or array, or `null`.

### criteria

`T`

Labels mapped to descriptions, or `null` for undescribed labels.

## Returns

[`ChoiceQuestion`](../interfaces/ChoiceQuestion.md)\<`T`>
