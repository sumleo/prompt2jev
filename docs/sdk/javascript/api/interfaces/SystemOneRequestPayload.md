# Interface: SystemOneRequestPayload

Request body for `POST /v1/systemone`, with the model resolved.

## Extends

* [`SystemOneRequest`](SystemOneRequest.md)

## Properties

<a id="sdk-model" />

### model

```ts theme={null}
model: string;
```

Model override; omitted values inherit `defaultModel`.

#### Overrides

[`SystemOneRequest`](SystemOneRequest.md).[`model`](SystemOneRequest.md#sdk-model)

***

<a id="sdk-questions" />

### questions

```ts theme={null}
questions: Questions;
```

Nonempty questions keyed by the names used to identify their answers.

#### Inherited from

[`SystemOneRequest`](SystemOneRequest.md).[`questions`](SystemOneRequest.md#sdk-questions)

***

<a id="sdk-state" />

### state

```ts theme={null}
state: EntryType;
```

Text, a JSON object or array, or `null` to evaluate.

#### Inherited from

[`SystemOneRequest`](SystemOneRequest.md).[`state`](SystemOneRequest.md#sdk-state)
