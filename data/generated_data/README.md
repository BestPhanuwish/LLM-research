# CharacterBox development data

`Harry_Potter.json` is a sanitised local copy of:

```text
CharacterBox/data/generated_data/Harry_Potter.json
```

Source commit: `5c19141ec04197bcdb2e7c7f7e235a5657952977`  
Upstream project: `https://github.com/Paitesanshi/CharacterBox`

The copy contains 50 LLM-generated Harry Potter scenes used for development and compatibility testing. A documented, manually verified subset may also be used in the final dual-source study. The `chunk` property was removed from every scene because it contains long source-book passages and is not consumed by CharacterBox's runtime loader.

For experiments using this data, the supplied and manually verified scene record—not outside franchise knowledge—is the evidence against which responses are evaluated. Its fictional content may have separate rights from CharacterBox's MIT-licensed software. Do not assume the software licence covers the dataset or republish it without a separate provenance/licensing review.
