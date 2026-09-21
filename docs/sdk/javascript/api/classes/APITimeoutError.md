# Class: APITimeoutError

The full response did not arrive within the timeout. A kind of `APIConnectionError`.

## Extends

* [`APIConnectionError`](APIConnectionError.md)

## Constructors

<a id="sdk-constructor" />

### Constructor

```ts theme={null}
new APITimeoutError(timeoutMs, options?): APITimeoutError;
```

#### Parameters

##### timeoutMs

`number`

##### options?

`ErrorOptions`

#### Returns

`APITimeoutError`

#### Overrides

[`APIConnectionError`](APIConnectionError.md).[`constructor`](APIConnectionError.md#sdk-constructor)

## Properties

<a id="sdk-timeoutms" />

### timeoutMs

```ts theme={null}
readonly timeoutMs: number;
```

Configured timeout in milliseconds.
