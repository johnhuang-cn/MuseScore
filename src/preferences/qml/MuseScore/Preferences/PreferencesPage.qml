/*
 * SPDX-License-Identifier: GPL-3.0-only
 * MuseScore-Studio-CLA-applies
 *
 * MuseScore Studio
 * Music Composition & Notation
 *
 * Copyright (C) 2021 MuseScore Limited
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
import QtQuick
import QtQuick.Controls

import Muse.Ui
import Muse.UiComponents

Rectangle {
    id: root
    height: parent.height
    color: ui.theme.backgroundSecondaryColor

    default property alias contentData: content.data

    // If false, the contentHeight of the Flickable is determined by the height of the content items.
    // When necessary, the page becomes scrollable automatically.
    // If true, the contentHeight of the Flickable is determined by the available height for the page.
    property bool contentFillsAvailableHeight: false

    readonly property int sectionsSpacing: 24
    readonly property int sideMargin: 30

    property NavigationSection navigationSection: null
    property int navigationOrderStart: 0

    signal hideRequested()

    function apply() {
        return true
    }

    function reset() {
    }

    function ensureContentVisibleRequested(contentRect) {
        // Follow the focus with scrolling only while the user navigates with the
        // keyboard. Focus changes caused by a mouse click or by a popup (e.g. a
        // font dropdown) closing must not move the page, otherwise the view jumps
        // back to the top right after a value has been selected.
        //
        // The check is deferred to the next event loop iteration because the
        // navigation highlight is turned on only after the control has been
        // activated (see NavigationController::navigateTo), so reading it
        // synchronously here would also suppress the legitimate keyboard case.
        Qt.callLater(function() {
            if (!navigationSection || !navigationSection.highlight) {
                return
            }

            if (flickable.contentY + flickable.height < contentRect.y + contentRect.height) {
                flickable.contentY += contentRect.y + contentRect.height - (flickable.contentY + flickable.height)
            } else if (flickable.contentY > contentRect.y) {
                flickable.contentY -= flickable.contentY - contentRect.y
            }
        })
    }

    StyledFlickable {
        id: flickable
        anchors.fill: parent

        readonly property real availableWidth: width - leftMargin - rightMargin
        readonly property real availableHeight: height - topMargin - bottomMargin

        readonly property bool isScrollable: contentHeight > availableHeight

        contentWidth: availableWidth
        contentHeight: root.contentFillsAvailableHeight ? availableHeight : content.childrenRect.height

        topMargin: root.sideMargin
        leftMargin: root.sideMargin
        rightMargin: root.sideMargin
        bottomMargin: root.sideMargin

        ScrollBar.vertical: StyledScrollBar { id: scrollBar }

        Item {
            id: content
            anchors.fill: parent
        }
    }

    GradientRectangle {
        id: topGradient
        visible: flickable.isScrollable

        anchors.top: flickable.top
        anchors.left: flickable.left
        anchors.right: flickable.right
        anchors.rightMargin: scrollBar.width

        height: root.sideMargin

        startColor: root.color
        endColor: "transparent"
    }

    GradientRectangle {
        id: bottomGradient
        visible: flickable.isScrollable

        anchors.left: flickable.left
        anchors.right: flickable.right
        anchors.rightMargin: scrollBar.width
        anchors.bottom: flickable.bottom

        height: root.sideMargin

        startColor: "transparent"
        endColor: root.color
    }
}
