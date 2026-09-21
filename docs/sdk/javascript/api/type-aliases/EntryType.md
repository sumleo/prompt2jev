# Type Alias: EntryType

```ts theme={null}
type EntryType = 
  | string
  | {
[key: string]: JsonValue;
}
  | JsonValue[]
  | null;
```

Text, a JSON object or array, or `null` for state, instructions, and criteria.
