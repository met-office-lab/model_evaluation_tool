const forest = require("./forest");


describe("helloWorld", () => {
    it("should return message", () => {
        expect(forest.helloWorld()).toEqual("Hello, World!")
    })
})


describe("decodedData", () => {
    it("maps empty data to empty data", () => {
        expect(forest.decodedData({
            encodedData: {
                start: [],
                frequency: [],
                length: []
            }
        })).toEqual({
            global_index: [],
            x: [],
        })
    })

    it("supports limits", () => {
        const actual = forest.decodedData({
            encodedData: {
                start: [1000],
                frequency: [1],
                length: [100]
            },
            limits: {
                start: 1095,
                end: 1100
            }
        })
        const expected = {
            global_index: [95, 96, 97, 98, 99],
            x: [1095, 1096, 1097, 1098, 1099]
        }
        expect(actual).toEqual(expected)
    })

    it("supports maxSize", () => {
        const actual = forest.decodedData({
            encodedData: {
                start: [1000],
                frequency: [1],
                length: [100]},
            limits: {
                start: 1095,
                end: 1100},
            maxPoints: 1
        })
        const expected = {
            global_index: [95],
            x: [1095],
        }
        expect(actual).toEqual(expected)
    })

    it("supports large data sets", () => {
        const actual = forest.decodedData({
            encodedData: {
                start: [0],
                frequency: [1],
                length: [1e8]
            },
            limits: {
                start: 1e7,
                end: 2e7
            },
            maxPoints: 2
        })
        const expected = {
            global_index: [1e7, 1.5e7],
            x: [1e7, 1.5e7],
        }
        expect(actual).toEqual(expected)
    })
})


describe("indexSpacing", () => {
    it.each`
        lower | upper  | maxPoints | expected
        ${0}  | ${99}  | ${100}    | ${1}
        ${0}  | ${10}  | ${5}      | ${2}
        ${0}  | ${300} | ${100}    | ${3}
        ${0}  | ${500} | ${100}    | ${5}
        ${0}  | ${1234} | ${10}    | ${123}
        ${0}  | ${1234} |  ${1}    | ${1234}
    `("linear lower=$lower upper=$upper maxPoints=$maxPoints -> $expected",
        ({lower, upper, maxPoints, expected}) => {
        expect(forest.indexSpacing({ lower, upper, maxPoints })).toBe(expected)
    })
    it.each`
        lower | upper  | maxPoints | expected
        ${0}  | ${1}   | ${100}    | ${1}
        ${0}  | ${99}  | ${100}    | ${1}
        ${0}  | ${300} | ${100}    | ${4}
        ${0}  | ${500} | ${100}    | ${8}
        ${0}  | ${1234} | ${10}    | ${128}
        ${0}  | ${1234} |  ${1}    | ${2048}
    `("exponential lower=$lower upper=$upper maxPoints=$maxPoints -> $expected",
        ({lower, upper, maxPoints, expected}) => {
        const algorithm = "exponential"
        const actual = forest.indexSpacing({ lower, upper, maxPoints, algorithm })
        expect(actual).toBe(expected)
    })
})

describe("findGlobalIndex", () => {
    it("should scan multiple blocks", () => {
        const blocks = [
            {
                globalIndex: 10,
                start: 50,
                frequency: 2,
                repeat: 5
            }
        ]
        const limits = {
            start: 0,
            end: 100
        }
        const actual = forest.findGlobalIndex({blocks, limits})
        const expected = {
            lower: 10,
            upper: 15
        }
        expect(actual).toEqual(expected)
    })
    it("should search inside blocks", () => {
        const blocks = [
            {
                globalIndex: 10,
                start: 50,
                frequency: 2,
                repeat: 5
            }
        ]
        const limits = {
            start: 55,
            end: 58
        }
        const actual = forest.findGlobalIndex({blocks, limits})
        const expected = {
            lower: 12,
            upper: 14
        }
        expect(actual).toEqual(expected)
    })
})

describe("decodeRLE", () => {
    it.each([
        [[], [], [], []],
        [[1], [1], [1], [1]],
        [[0], [10], [2], [0, 10]],
        [[5], [10], [2], [5, 15]],
        [[1, 2], [1, 1], [1, 1], [1, 2]],
    ])("given %p, %p, %p should return %p",
        (starts, frequencies, repeats, expected) => {
        let actual = forest.decodeRLE(starts, frequencies, repeats)
        expect(actual).toEqual(expected)
    })
})


describe("algorithm to space points", () => {
    it("does a thing", () => {
        const lower = 100
        const upper = 200
        const multiplesOf = 95
        const actual = forest.evenlySpacedIndex({lower, upper, multiplesOf})
        const expected = [190]
        expect(actual).toEqual(expected)
    })
})

describe("filterCompressed", () => {
    it("removes periods outside interval", () => {
        let data = {
            start: [1],
            frequency: [2],
            repeat: [3]
        }
        let settings = {start: 0, end: 0}
        let actual  = forest.blocks(data)
        let expected = [
            {start: 1, frequency: 2, repeat: 3}
        ]
        expect(actual).toEqual(expected)
    })

    it.each`
        left                        | right                     | expected
        ${ {start: 0, end: 43} }    | ${ {start: 42, end: 43} } | ${true}
        ${ {start: 43.1, end: 44} } | ${ {start: 42, end: 43} } | ${false}
    `("given $left, $right returns $expected", ({left, right, expected}) => {
        expect(forest.overlap(left)(right)).toEqual(expected)
    })

    it.each`
        block                                     | expected
        ${ {start: 42, frequency: 1, repeat: 1} } | ${ {start: 42, end: 43} }
    `("given $block returns $expected", ({block, expected}) => {
        expect(forest.toRange(block)).toEqual(expected)
    })
})
