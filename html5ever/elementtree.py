import xml.etree.ElementTree as ET


def qname(namespace_url, local_name):
    return '{%s}%s' % (namespace_url, local_name) if namespace_url else local_name


class TreeBuilder(object):
    def __init__(self):
        self.parent_map = {}

    def new_document(self):
        return ET.ElementTree()

    def new_element(self, namespace_url, local_name):
        return ET.Element(qname(namespace_url, local_name))

    def element_add_template_contents(self, element):
        # Store the template contents as children of the <template> element itself.
        return element

    def element_add_attribute_if_missing(self, element, namespace_url, local_name, value):
        name = qname(namespace_url, local_name)
        if element.get(name) is None:
            element.set(name, value)

    def new_comment(self, data):
        return ET.Comment(data)

    def append_doctype_to_document(self, document, name, public_id, system_id):
        document.doctype = (name, public_id, system_id)

    def append_node(self, parent, new_child):
        if isinstance(parent, ET.ElementTree):
            # Drop comments outside the root element
            if new_child.tag != ET.Comment:
                assert parent.getroot() is None
                parent._root = new_child
        else:
            parent.append(new_child)
        self.parent_map[new_child] = parent

    def append_text(self, parent, data):
        if len(parent):
            last_child = parent[-1]
            if last_child.tail is None:
                last_child.tail = data
            else:
                last_child.tail += data
        else:
            if parent.text is None:
                parent.text = data
            else:
                parent.text += data

    def insert_node_before_sibling(self, sibling, new_sibling):
        parent = self.parent_map.get(sibling)
        if parent is None:
            return False
        position = list(parent).index(sibling)
        parent.insert(position, new_sibling)
        return True

    def insert_text_before_sibling(self, sibling, data):
        parent = self.parent_map.get(sibling)
        if parent is None:
            return False
        position = list(parent).index(sibling)
        if position > 0:
            previous_sibling = parent[position - 1]
            if previous_sibling.tail is None:
                previous_sibling.tail = data
            else:
                previous_sibling.tail += data
        else:
            if parent.text is None:
                parent.text = data
            else:
                parent.text += data
        return True

    def reparent_children(self, parent, new_parent):
        new_parent.extend(parent)
        for child in list(parent.children):
            self.parent_map[child] = new_parent
            parent.remove(child)

    def remove_from_parent(self, node):
        parent = self.parent_map.pop(node)
        if parent is not None:
            parent.remove(node)
