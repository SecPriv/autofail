// file: SharkBridge.kt
@file:JvmName("SharkBridge")

package com.example.spill   // ← change to match your package name

import shark.HeapField
import shark.Hprof
import shark.HprofHeapGraph
import shark.HeapGraph
import shark.HeapObject.HeapClass
import shark.HeapObject.HeapInstance
import java.io.File
import java.util.LinkedHashSet

/**
 * Java-friendly helpers for Shark 2.x (e.g. 2.14)
 *
 * In app/build.gradle:
 *   debugImplementation("com.squareup.leakcanary:shark-hprof:2.14")
 *   debugImplementation("com.squareup.leakcanary:shark-graph:2.14")
 *
 *   This class parses the heap and retrieves the value of the object we search for
 */
object SharkBridge {

    data class PopupWindowInfo(
        val index: Int,
        val width: Int,
        val height: Int
    )

    // ---------- Public API (callable from Java) ----------

    @JvmStatic
    fun countInstances(hprofFile: File, className: String): Int {
        val graph = openGraph(hprofFile) ?: return 0
        val cls: HeapClass = graph.findClassByName(className) ?: return 0
        var count = 0
        val iter: Iterator<HeapInstance> = cls.instances.iterator()
        while (iter.hasNext()) {
            iter.next()
            count++
        }
        return count
    }

    @JvmStatic
    fun countBitmaps(hprofFile: File): Int =
        countInstances(hprofFile, "android.graphics.Bitmap")

    @JvmStatic
    fun totalBitmapBytes(hprofFile: File): Long {
        val graph = openGraph(hprofFile) ?: return 0L
        val cls: HeapClass = graph.findClassByName("android.graphics.Bitmap") ?: return 0L
        var total = 0L
        val iter: Iterator<HeapInstance> = cls.instances.iterator()
        while (iter.hasNext()) {
            val inst: HeapInstance = iter.next()
            val bytes: Long =
                inst.longField("android.graphics.Bitmap", "mByteCount")
                    ?: inst.longField("android.graphics.Bitmap", "mAllocationByteCount")
                    ?: 0L
            total += bytes
        }
        return total
    }

    /**
     * Distinct Activity class names present in the heap dump.
     */
    @JvmStatic
    fun listActivityClassNames(hprofFile: File): List<String> {
        val graph = openGraph(hprofFile) ?: return emptyList()
        val base: HeapClass = graph.findClassByName("android.app.Activity") ?: return emptyList()
        val names = LinkedHashSet<String>()
        val iter: Iterator<HeapInstance> = base.instances.iterator()
        while (iter.hasNext()) {
            val inst: HeapInstance = iter.next()
            val name: String? = inst.instanceClassName()
            if (name != null) names.add(name)
        }

        return names.toList()
    }

    /**
     * Read a long field from the first instance of className (owner = declaring class).
     */
    @JvmStatic
    fun readFirstInstanceLongField(
        hprofFile: File,
        className: String,
        ownerClassName: String,
        fieldName: String
    ): Long? {
        val graph = openGraph(hprofFile) ?: return null
        val cls: HeapClass = graph.findClassByName(className) ?: return null
        val it: Iterator<HeapInstance> = cls.instances.iterator()
        if (!it.hasNext()) return null
        val first: HeapInstance = it.next()
        val result = first.longField(ownerClassName, fieldName)
        return result
    }

    @JvmStatic
    fun getAutofillPopupWindowSizes(hprofFile: File): List<PopupWindowInfo> {
        val graph = openGraph(hprofFile) ?: return emptyList()
        val cls = graph.findClassByName("android.view.autofill.AutofillPopupWindow") ?: return emptyList()

        val result = mutableListOf<PopupWindowInfo>()
        var index = 0
        val it = cls.instances.iterator()
        while (it.hasNext()) {
            val popupInst = it.next()

            // mWindowLayoutParams field (object reference)
            val lpObjId = popupInst.objectFieldId(
                "android.view.autofill.AutofillPopupWindow",
                "mWindowLayoutParams"
            ) ?: continue

            val lp = graph.findObjectById(lpObjId) as? HeapInstance ?: continue

            // width/height come from ViewGroup.LayoutParams
            val width = lp.intFieldAnyDecl("width") ?: -1
            val height = lp.intFieldAnyDecl("height") ?: -1

            result.add(PopupWindowInfo(index, width, height))
            index++
        }
        return result
    }

    /** Helper: get the objectId of an object-typed field (compatible with Shark 2.x) */
    private fun HeapInstance.objectFieldId(ownerClass: String, fieldName: String): Long? {
        val iter = this.readFields().iterator()
        while (iter.hasNext()) {
            val f = iter.next()
            if (f.declaringClass.name == ownerClass && f.name == fieldName) {
                val value = f.value
                return if (!value.isNullReference) value.asObjectId else null
            }
        }
        return null
    }

    private fun HeapInstance.intFieldAnyDecl(fieldName: String): Int? {
        val iter = this.readFields().iterator()
        while (iter.hasNext()) {
            val f = iter.next()
            if (f.name == fieldName) return f.value.asInt
        }
        return null
    }

    // Add this helper (near your other helpers)

    // ---------- Internals ----------

    private fun openGraph(hprofFile: File): HeapGraph? {
        val source = Hprof.open(hprofFile)
        return HprofHeapGraph.indexHprof(source)
    }

    private fun HeapInstance.longField(ownerClass: String, fieldName: String): Long? {
        val fields: Sequence<HeapField> = this.readFields()
        val iter: Iterator<HeapField> = fields.iterator()
        while (iter.hasNext()) {
            val f: HeapField = iter.next()
            if (f.declaringClass.name == ownerClass && f.name == fieldName) {
                return f.value.asLong
            }
        }
        return null
    }

    private fun HeapInstance.instanceClassName(): String? {
        val clsId = this.instanceClassId ?: return null
        val obj = this.graph.findObjectById(clsId)
        val heapClass = obj as? HeapClass ?: return null
        return heapClass.name
    }
}
