# Interface: ChoiceResponse<T>

A selected label and its probabilities.

## Type Parameters

### T

`T` *extends* [`ChoiceCriteria`](../type-aliases/ChoiceCriteria.md) = [`ChoiceCriteria`](../type-aliases/ChoiceCriteria.md)

## Properties

<a id="sdk-choice" />

### choice

```ts theme={null}
readonly choice: keyof T & string;
```

The selected label.

***

<a id="sdk-confidence" />

### confidence

```ts theme={null}
readonly confidence: number;
```

Reported confidence in the selected label.

***

<a id="sdk-probabilities" />

### probabilities

```ts theme={null}
readonly probabilities: { readonly [label in string | number | symbol]: number };
```

Probabilities keyed by label.

***

<a id="sdk-type" />

### type

```ts theme={null}
readonly type: "choice";
```
