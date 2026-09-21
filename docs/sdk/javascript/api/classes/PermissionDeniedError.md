# Class: PermissionDeniedError

HTTP 403: access is denied.

## Extends

* [`APIError`](APIError.md)

## Constructors

<a id="sdk-constructor" />

### Constructor

```ts theme={null}
new PermissionDeniedError(
   status, 
   body, 
   headers, 
   message?
): PermissionDeniedError;
```

#### Parameters

##### status

`number`

##### body

`unknown`

##### headers

`Headers`

##### message?

`string`

#### Returns

`PermissionDeniedError`

#### Inherited from

[`APIError`](APIError.md).[`constructor`](APIError.md#sdk-constructor)

## Properties

<a id="sdk-body" />

### body

```ts theme={null}
readonly body: unknown;
```

Parsed JSON, response text, or `undefined` for an empty body.

#### Inherited from

[`APIError`](APIError.md).[`body`](APIError.md#sdk-body)

***

<a id="sdk-headers" />

### headers

```ts theme={null}
readonly headers: Headers;
```

HTTP response headers.

#### Inherited from

[`APIError`](APIError.md).[`headers`](APIError.md#sdk-headers)

***

<a id="sdk-requestid" />

### requestId

```ts theme={null}
readonly requestId: string | undefined;
```

Request ID from `x-typesafe-request-id`, or `undefined` when absent.

#### Inherited from

[`APIError`](APIError.md).[`requestId`](APIError.md#sdk-requestid)

***

<a id="sdk-status" />

### status

```ts theme={null}
readonly status: number;
```

HTTP response status code.

#### Inherited from

[`APIError`](APIError.md).[`status`](APIError.md#sdk-status)

## Methods

<a id="sdk-fromresponse" />

### fromResponse()

```ts theme={null}
static fromResponse(
   status, 
   body, 
   headers
): APIError;
```

Create the error subclass for an HTTP status code.

#### Parameters

##### status

`number`

##### body

`unknown`

##### headers

`Headers`

#### Returns

[`APIError`](APIError.md)

#### Inherited from

[`APIError`](APIError.md).[`fromResponse`](APIError.md#sdk-fromresponse)
