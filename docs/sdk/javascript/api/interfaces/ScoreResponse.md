# Interface: ScoreResponse<T>

An expected score with its rubric and probabilities.

## Type Parameters

### T

`T` *extends* [`ScoreCriteria`](../type-aliases/ScoreCriteria.md) = [`ScoreCriteria`](../type-aliases/ScoreCriteria.md)

## Properties

<a id="sdk-confidence" />

### confidence

```ts theme={null}
readonly confidence: number;
```

Reported confidence in the score.

***

<a id="sdk-legend" />

### legend

```ts theme={null}
readonly legend: ScoreLegend<T>;
```

Rubric descriptions keyed by score.

***

<a id="sdk-probabilities" />

### probabilities

```ts theme={null}
readonly probabilities: { readonly [score in number | `${number}`]: number };
```

Probabilities keyed by score.

***

<a id="sdk-score" />

### score

```ts theme={null}
readonly score: number;
```

Expected score, which may fall between integer rubric levels.

***

<a id="sdk-type" />

### type

```ts theme={null}
readonly type: "score";
```
