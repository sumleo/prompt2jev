# Function: score()

```ts theme={null}
function score<T>(instructions, criteria): ScoreQuestion<T>;
```

Create a score question using an ordered rubric.

## Type Parameters

### T

`T` *extends* [`ScoreCriteria`](../type-aliases/ScoreCriteria.md)

## Parameters

### instructions

[`EntryType`](../type-aliases/EntryType.md)

The question as text, a JSON object or array, or `null`.

### criteria

`T`

At least two descriptions indexed by score from zero; entries may be `null`.

## Returns

[`ScoreQuestion`](../interfaces/ScoreQuestion.md)\<`T`>
