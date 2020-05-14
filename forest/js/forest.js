const redux = require('redux')

const ns = {}

const SET_GLOBAL_INDEX = "SET_GLOBAL_INDEX"
const NEXT = "NEXT"
const PREVIOUS = "PREVIOUS"

const reducer = ns.reducer = (state={}, action) => {
    switch (action.type) {
        case SET_GLOBAL_INDEX:
            return Object.assign({}, state, {
                global_index: action.payload
            })
        case NEXT:
            if (typeof state.global_index === "undefined") {
                return state
            }
            return Object.assign({}, state, {
                global_index: state.global_index + 1
            })
        case PREVIOUS:
            if (typeof state.global_index === "undefined") {
                return state
            }
            return Object.assign({}, state, {
                global_index: state.global_index - 1
            })
        default:
            return state
    }
    return state
}

// Filter SET_GLOBAL_INDEX actions
const middleware = store => next => action => {
    if (action.type !== SET_GLOBAL_INDEX) {
        return next(action)
    } else {
        let state = store.getState()
        if (action.payload !== state.global_index) {
            return next(action)
        }
    }
}

const store = ns.STORE = redux.createStore(reducer, redux.applyMiddleware(middleware))

// Work-around to connect BokehJS to ReduxJS
const listeners = {}
ns.add_subscriber = (uid, listener) => {
    if ( !(uid in listeners) ) {
        listeners[uid] = listener
        return store.subscribe(listener)
    }

}

// Decoded data
ns.decodedData = ({encodedData, limits, maxPoints = 100, algorithm = "linear"}) => {

    // Convert encoded data into array of "blocks"
    let blocks = asBlocks({
        start: encodedData['start'],
        frequency: encodedData['frequency'],
        repeat: encodedData['length'],
    })

    // Annotate blocks with index relative to full array
    blocks.reduce((counter, block) => {
        block.globalIndex = counter
        return counter + block.repeat
    }, 0)


    let overlap = overlapFunc(limits)
    let filterMethod = function(block) {
        return overlap(toRange(block))
    }

    let validBlocks = blocks.filter(filterMethod)
    if (validBlocks.length === 0) {
        return {
            global_index: [],
            x: []
        }
    }

    // Find visible index range
    let index = findGlobalIndex({blocks: validBlocks, limits})
    let spacing = indexSpacing({...index, maxPoints, algorithm})

    // Algorithm to evenly space indices
    let global_index = evenlySpacedIndex({...index, multiplesOf: spacing })

    console.log({index, spacing, global_index})

    // Find x from global_index
    let x = global_index.map((globalIndex) => {
        // Find block
        for (let i=0; i<validBlocks.length; i++) {
            let block = validBlocks[i]
            if (globalIndex < block.globalIndex) {
                continue
            }
            if (globalIndex > (block.globalIndex + block.repeat)) {
                continue
            }
            return getGlobalPosition({block, globalIndex})
        }
    })
    return {global_index, x}
}

let indexSpacing = ns.indexSpacing = function({
        lower, upper, maxPoints, algorithm = 'linear'}) {
    if (algorithm === "linear") {
        let N = upper - lower
        spacing = Math.floor(N / maxPoints)
    } else {
        let N = upper - lower
        let exponent = Math.ceil(Math.log2(N / maxPoints))
        spacing = 2 ** exponent
    }

    // Apply minimum spacing
    if (spacing < 1) {
        spacing = 1
    }
    return spacing
}

// Restrict index to multiples of a number that fall inside range
let evenlySpacedIndex = ns.evenlySpacedIndex = function({lower, upper, multiplesOf}) {
    let iMin = Math.floor(lower / multiplesOf)
    let iMax = Math.floor(upper / multiplesOf)
    let indices = []
    for (let i=iMin; i<=iMax; i++) {
        let value = i * multiplesOf
        if ((value >= lower) && (value < upper)) {
            indices.push(value)
        }
    }
    return indices
}

let findGlobalIndex = ns.findGlobalIndex = function({blocks, limits}) {
    let indices

    // Get index extent of blocks
    const validMin = 0
    const validMax = blocks.map((b) => { return b.globalIndex + b.repeat })
                           .reduce((a, i) => Math.max(a, i), 0)

    // Find lower index
    indices = blocks.map((block) => {
        return getGlobalIndex({block, position: limits.start})
    })
    const lower = indices.reduce((a, i) => Math.min(a, i), validMax)

    // Find upper index
    indices = blocks.map((block) => {
        return getGlobalIndex({block, position: limits.end})
    })
    const upper = indices.reduce((a, i) => Math.max(a, i), validMin)

    return { lower, upper }
}

// Estimate global index of point inside block
let getGlobalIndex = function({block, position}) {
    return block.globalIndex + getIndex({block, position})
}

// Estimate index of point inside block
let getIndex = function({block, position}) {
    if (position < block.start) {
        return 0
    }
    if (position > (block.start + (block.repeat * block.frequency))) {
        return block.repeat
    }
    return Math.floor((position - block.start) / block.frequency)
}

// Estimate position of index inside block
let getGlobalPosition = function({block, globalIndex}) {
    let index = globalIndex - block.globalIndex
    return getPosition({block, index})
}

// Estimate position of index inside block
let getPosition = function({block, index}) {
    if (index > block.repeat) {
        return block.start + (block.repeat * block.frequency)
    }
    if (index < 0) {
        return block.start
    }
    return block.start + (index * block.frequency)
}

/**
 * Remove blocks of compressed data outside of range
 */
let asBlocks = ns.blocks = (compressed) => {
    let array = []
    let length = compressed.start.length
    for (let i=0; i<length; i++) {
        array.push({
            start: compressed.start[i],
            frequency: compressed.frequency[i],
            repeat: compressed.repeat[i],
        })
    }
    return array
}
let toRange = ns.toRange = (block) => {
    return {
        start: block.start,
        end: block.start + (block.repeat * block.frequency)
    }
}

// Curried overlapping interval function
let overlapFunc = ns.overlap = (first) => {
    return (second) => {
        return (
            (first.end >= second.start) &&
            (second.end >= first.start)
        )
    }
}


// Throttle
const throttle = ns.throttle = function(callable, milliseconds) {
    let throttled
    let value
    return function() {
        const args = arguments
        const context = this
        if (!throttled) {
            value = callable.apply(context, args)
            setTimeout(() => throttled = false, milliseconds)
        }
        // Most recent value
        return value
    }
}

// Prepare filtered-data
ns.filterXRange = throttle(function(times, x_range) {
    let x = []
    let originalIndex = []
    for (let i=0; i<times.length; i++) {
        let t = times[i]
        if ((t > x_range.start) & (t < x_range.end)) {
            x.push(times[i])
            originalIndex.push(i)
        }
    }
    return {
        x: x,
        index: originalIndex
    }
}, 200)


ns.throttledUpdate = throttle(function(source, data) {
    source.data = data
    source.change.emit()
}, 200)


ns.helloWorld = () => "Hello, World!"


// Populate variable options from dataset value
ns.link_selects = function(dataset_select, variable_select, source) {
    let label = dataset_select.value;
    if (label !== "") {
        let index = source.data['datasets'].indexOf(label)
        let defaults = ["Please specify"];
        variable_select.options = defaults.concat(
            source.data['variables'][index]);
    }
}

// Decode run-length-encoded datetimes
ns.decodeRLE = function(starts, frequencies, repeats) {
    let array = [];
    for (let p=0; p<starts.length; p++) {
        let start = starts[p];
        let frequency = frequencies[p];
        let length = repeats[p];
        for (let i=0; i<length; i++) {
            array.push(start + i * frequency)
        }
    }
    return array;
}

module.exports = ns
