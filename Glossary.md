# Glossary for Names regarding PDFs

## Definitions

* Session
  * Meeting of BR
  * Numbered from 1 to x (= Session Number)
  * e.g 990 or 973

* TOP (Tagesordnungspunkt)
  * Determined by number and (if present) the Subpart and (if present) Dot/Bracket
    * e.g. 32. , 34. a) (but not 34. alone ) , 23. e)
  * Counties/Bundesländer can vote for a TOP either with Zustimmen (Yes), Ablehnen (No), or Enthalten (out/abstain)

* Number of TOP
  * Number part of TOP, can be same as TOP
  * Always ends with '.'
  * Present for all TOPs
    * e.g. 32., 34. (of 34. a) ) , 23.

* Subpart of TOP
  * Letter behind some TOPs, but not all
  * Always ends with ')'
  * Not present for all TOPs, if TOP only has its number
    * e.g. a) (of 34. a) ) , e)
    * but 32. has no subpart

* Chunk
  * One group of words that pdfcutter recognizes as one Selection
    * depends on `pdftohtml -xml` output
  * TOP Chunk := Its Subpart Chunk, because Number and Subpart Chunk can differ if they are not present in the same column
      * Determine which Subpart Chunk is the TOP Chunk can be hard if number and subpart not in same chunk
  * If TOP has only number and number is split into n Chunks, then TOP Chunk := highest chunk with (first) part of the number
    * Still Subpart Chunk if Subpart present

* Selection String Format
  * Selection(left, right, width, height) w.r.t. `pdftohtml -xml`
  * `pdftohtml -xml` returns (top, left, width, height)
    * right from Selection is left+width of *complete* chunk, not only matched part
  * Selection contains always *whole* chunk content, not only matched one
  * Selection *always* List, can be empty and can be used like a list.
    * Sorted by relative page height `top`, not by absolute Document Height `doc_top`
    * But e.g. `Selection.below` also checks for `doc_top`, not `top`

* Highest Selection from some Selections
  * First Selection that occurs in PDF
  * <=> Selection with smallest `doc_top` value

* Lowest Selection from some Selections
  * Last Selection that occurs in PDF
  * <=> Selection with highest `doc_top` value

* Upper Border of some Selections S
  * Some Selection b, such that all filtered Selections from S' are strictly below b
  * S' can be empty
  * Strict, because `cutter.below(selection)` is strict, never contains `selection`
    * To circumvent this, do:

* Next TOP
  * Numerical/Subpart wise next TOP
  * e.g. next TOP of 1. is 2. a), next TOP of 2. b) is 3.

* Next Direct TOP
  * Some Counties dont order TOPs by Number/Subpart (e.g. NS 988 , RP)
    * Then we need to find the next direct TOP as lower bound  , i.e. the TOP that follows current TOP in PDF
  * e.g. next TOP of 1. is 2. a), but next direct TOP of 1. might be 30. 

```
            nonStrictSelections = self.cutter.all().filter(
                doc_top__gte=selection.doc_top - 1, #Upper Border a little bit higher -> Non-Strict
            )
```


## Relations

* 1 Session has 1 Session Number
* 1 Session has n TOPs
* 1 TOP has 1 Number
* 1 TOP has 0-1 Subparts
* 1 Number has n TOPs
* 1 Subpart has n TOPs
* 1 Selection has *exactly* n Chunks, not just matching parts of them
  * Selection is always List, so
    * when we talk about 1 Chunk, then we say Selection
    * when we talk about 0-n Chunks, then we say Selections, although its one Selection-Object
    
* 1 Chunk can be in n Selections
* 1 Number can be in n Chunks
