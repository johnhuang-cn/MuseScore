/* SPDX-License-Identifier: GPL-3.0-only */
#pragma once

#include <cmath>
#include "draw/types/font.h"
#include "dom/engravingitem.h"
#include "dom/keysig.h"
#include "dom/measure.h"
#include "dom/staff.h"
#include "style/style.h"

namespace mu::engraving::rendering::score {
// Return the unscaled font. Drawing/layout callers keep their existing magS
// convention, so note bounds, beams, rests and slur/tie anchors stay consistent.
inline muse::draw::Font jianpuFont(const EngravingItem* item)
{
    const MStyle& style = item->style();

    // App-wide preference (Preferences -> Appearance -> Jianpu text);
    // falls back to the score style when no configuration is available.
    muse::String family;
    double size = 0.0;
    const std::shared_ptr<IEngravingConfiguration>& conf = item->configuration();
    if (conf) {
        family = conf->jianpuFontFamily();
        size = conf->jianpuFontSize();
    }
    if (family.empty()) {
        family = style.styleSt(Sid::jianpuFontFace);
    }
    if (family.empty()) {
        family = muse::String(u"Arial");
    }
    if (!std::isfinite(size) || size <= 0.0) {
        size = style.styleD(Sid::jianpuFontSize);
    }

    muse::draw::Font font(muse::draw::Font::FontFamily(family), muse::draw::Font::Type::Text);
    font.setPointSizeF(std::isfinite(size) && size > 0.0 ? size : 12.0);
    font.setBold(style.styleB(Sid::jianpuFontBold));
    font.setItalic(style.styleB(Sid::jianpuFontItalic));
    return font;
}

// Jianpu prints the "1=X" key signature only where it carries information:
// the first measure of the score and real key changes (modulation). The
// generated header key sig repeated at each system start stays hidden.
inline bool jianpuKeySigVisible(const KeySig* item)
{
    if (item->isCourtesy()) {
        return false;
    }
    const Measure* meas = item->measure();
    if (!meas) {
        return false;
    }
    const Measure* prevMeas = meas->prevMeasure();
    if (!prevMeas) {
        return true;  // first measure: keep the key signature display
    }
    // The musical key comes from the linked standard staff (primaryStaff),
    // same source as the movable-do key name mapping.
    const Staff* st = item->staff();
    const Staff* src = (st && st->primaryStaff()) ? st->primaryStaff() : st;
    return src->key(prevMeas->tick()) != src->key(meas->tick());
}
}
