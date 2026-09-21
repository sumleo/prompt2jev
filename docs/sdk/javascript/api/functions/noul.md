# Function: noul()

```ts theme={null}
function noul(instructions?, criteria?): NoulQuestion;
```

Create a yes/no question with optional descriptions for either outcome.

## Parameters

### instructions?

[`EntryType`](../type-aliases/EntryType.md) = `null`

The question as text, a JSON object or array; defaults to `null`.

### criteria?

\| \{
`false?`: [`EntryType`](../type-aliases/EntryType.md);
`true?`: [`EntryType`](../type-aliases/EntryType.md);
}
\| `null`

Optional descriptions of the yes and no outcomes.

#### Type Literal

\{
`false?`: [`EntryType`](../type-aliases/EntryType.md);
`true?`: [`EntryType`](../type-aliases/EntryType.md);
}

Optional descriptions of the yes and no outcomes.

##### false?

[`EntryType`](../type-aliases/EntryType.md)

Description of the no outcome.

##### true?

[`EntryType`](../type-aliases/EntryType.md)

Description of the yes outcome.

***

`null`

## Returns

[`NoulQuestion`](../interfaces/NoulQuestion.md)
